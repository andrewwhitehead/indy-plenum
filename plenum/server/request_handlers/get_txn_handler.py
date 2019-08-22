from plenum.common.constants import DOMAIN_LEDGER_ID, DATA, TXN_TYPE, GET_TXN, MULTI_SIGNATURE, AUDIT_LEDGER_ID, \
    AUDIT_TXN_STATE_ROOT, TXN_PAYLOAD
from plenum.common.exceptions import InvalidClientRequest
from plenum.common.messages.node_messages import RequestNack, Reply
from plenum.common.request import Request
from plenum.common.txn_util import get_seq_no
from plenum.common.types import f
from plenum.server.database_manager import DatabaseManager
from plenum.server.request_handlers.handler_interfaces.read_request_handler import ReadRequestHandler
from stp_core.common.log import getlogger

logger = getlogger()


class GetTxnHandler(ReadRequestHandler):

    def __init__(self, node, database_manager: DatabaseManager):
        super().__init__(database_manager, GET_TXN, None)
        self.node = node

    def static_validation(self, request: Request):
        ledger_id = request.operation.get(f.LEDGER_ID.nm, DOMAIN_LEDGER_ID)
        if ledger_id not in self.node.ledger_ids:
            raise InvalidClientRequest(request.identifier, request.reqId,
                                       'Invalid ledger id {}'.format(ledger_id))
        super().static_validation(request)

    def get_result(self, request: Request):
        ledger_id = request.operation.get(f.LEDGER_ID.nm, DOMAIN_LEDGER_ID)
        db = self.database_manager.get_database(ledger_id)
        if db is None:
            return RequestNack(request.identifier, request.reqId,
                               'Invalid ledger id {}'.format(ledger_id))

        seq_no = request.operation.get(DATA)

        try:
            txn = self.node.getReplyFromLedger(db.ledger, seq_no)
            audit_ledger = self.database_manager.get_ledger(AUDIT_LEDGER_ID)
            audit_seq_no = audit_ledger.size
            state_root = None
            for seq_no in reversed(range(1, audit_seq_no + 1)):
                audit_txn = audit_ledger.getBySeqNo(seq_no)
                state_root = audit_txn[TXN_PAYLOAD][DATA][AUDIT_TXN_STATE_ROOT].get(ledger_id, None)
                if state_root:
                    break
            multi_sig = self.database_manager.bls_store.get(state_root)
            txn.result[MULTI_SIGNATURE] = multi_sig.as_dict()
        except KeyError:
            txn = None

        if txn is None:
            logger.debug(
                "{} can not handle GET_TXN request: ledger doesn't "
                "have txn with seqNo={}".format(self, str(seq_no)))

        result = {
            f.IDENTIFIER.nm: request.identifier,
            f.REQ_ID.nm: request.reqId,
            TXN_TYPE: request.operation[TXN_TYPE],
            DATA: None
        }

        if txn:
            result[DATA] = txn.result
            result[f.SEQ_NO.nm] = get_seq_no(txn.result)

        return result
