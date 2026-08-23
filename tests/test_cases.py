from matter_context.application.cases import CaseListItem, CasesList, EmptyCasesService
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
