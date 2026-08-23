from matter_context.application.cases import CaseListItem, CasesList, EmptyCasesService, PersistedCasesService
from matter_context.application.matters import MatterService
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork
from matter_context.ui.cases import CasesViewModel


class OneCaseService:
    def list_cases(self) -> CasesList:
        return CasesList((CaseListItem("case-1", "Example case"),))


def test_empty_cases_service_returns_immutable_empty_result() -> None:
    result = EmptyCasesService().list_cases()

    assert result.items == ()


def test_view_model_maps_empty_application_result_without_qt() -> None:
    state = CasesViewModel(EmptyCasesService()).load()

    assert state.title == "Cases"
    assert state.empty_heading == "No cases yet"
    assert state.primary_action_text == "Create a case"


def test_view_model_preserves_case_read_models() -> None:
    state = CasesViewModel(OneCaseService()).load()

    assert state.empty_heading is None
    assert state.cases[0].title == "Example case"


def test_persisted_cases_service_lists_durable_matters(tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'cases.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    MatterService(factory).create_matter("A durable matter", reference="MC-2")

    result = PersistedCasesService(factory).list_cases()

    assert result.items == (CaseListItem(result.items[0].identifier, "A durable matter", "MC-2", "active"),)
