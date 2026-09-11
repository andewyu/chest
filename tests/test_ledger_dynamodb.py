from decimal import Decimal

from chest.store.ledger import Entry, LedgerStore


class FakeDynamoTable:
    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}

    def put_item(self, *, Item: dict):
        self.items[(Item["account_id"], Item["id"])] = Item

    def query(self, **_kwargs):
        return {"Items": list(self.items.values())}

    def delete_item(self, *, Key: dict):
        self.items.pop((Key["account_id"], Key["id"]), None)


def dynamo_store() -> tuple[LedgerStore, FakeDynamoTable]:
    table = FakeDynamoTable()
    store = object.__new__(LedgerStore)
    store.account_id = "acct_test"
    store._backend = "dynamodb"
    store._table = table
    return store, table


def test_dynamodb_serializes_currency_without_floats():
    store, table = dynamo_store()
    entry = Entry(amount=-47.25, kind="expense", memo="hoses", occurred_on="2026-09-10")

    store.log(entry)

    stored_amount = table.items[("acct_test", entry.id)]["amount"]
    assert isinstance(stored_amount, Decimal)
    assert stored_amount == Decimal("-47.25")


def test_dynamodb_can_discard_a_pending_transaction():
    store, table = dynamo_store()
    entry = Entry(amount=-47.25, kind="expense", memo="hoses", occurred_on="2026-09-10")
    store.log(entry)

    assert store.discard(entry.id)
    assert ("acct_test", entry.id) not in table.items
