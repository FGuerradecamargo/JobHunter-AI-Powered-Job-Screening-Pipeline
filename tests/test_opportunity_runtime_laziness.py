from pathlib import Path


PAGE = Path(
    "pages/1_Opportunities.py"
)


def source():
    return PAGE.read_text(
        encoding="utf-8"
    )


def test_jobs_page_does_not_construct_analysis_service_before_candidate_gates():
    text = source()

    candidate_gate = text.index(
        "if not active_user.candidate_id:"
    )

    assert (
        "CandidateJobAnalysisService()"
        not in text[:candidate_gate]
    )


def test_analysis_service_is_built_only_for_requested_or_running_search():
    text = source()

    lazy_marker = text.index(
        "_analysis_requested ="
    )

    constructor = text.index(
        "CandidateJobAnalysisService()",
        lazy_marker,
    )

    search_form = text.index(
        'with st.form("opportunity_search_controls")'
    )

    assert (
        lazy_marker
        < constructor
        < search_form
    )

    lazy_block = text[
        lazy_marker:
        search_form
    ]

    assert (
        'st.session_state.get('
        in lazy_block
    )

    assert (
        '"scan_requested"'
        in lazy_block
    )

    assert (
        '== "running"'
        in lazy_block
    )

    assert (
        "search_scope"
        in lazy_block
    )


def test_find_button_does_not_require_eager_analysis_service():
    text = source()

    form_start = text.index(
        'with st.form("opportunity_search_controls")'
    )

    form_end = text.index(
        'if analysis_configuration_error:',
        form_start,
    )

    form = text[
        form_start:
        form_end
    ]

    assert (
        "analysis_service is None"
        not in form
    )


def test_retry_button_can_trigger_lazy_service_initialization():
    text = source()

    retry_start = text.index(
        'st.button(',
        text.index(
            '"Try again"'
        ) - 30,
    )

    retry_end = text.index(
        "\n\n",
        retry_start,
    )

    retry = text[
        retry_start:
        retry_end
    ]

    assert (
        "request_opportunity_scan"
        in retry
    )

    assert (
        "disabled=analysis_service is None"
        not in retry
    )
