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



def test_prepare_application_service_is_not_built_during_passive_page_render():
    text = source()

    render_job = text.index(
        "def render_job("
    )

    before_render_job = text[
        :render_job
    ]

    assert (
        "build_production_prepare_application_service()"
        not in before_render_job
    )


def test_prepare_application_service_is_built_only_after_explicit_action():
    text = source()

    render_start = text.index(
        "def render_job("
    )

    prepare_button = text.index(
        'prepare_requested = st.button(',
        render_start,
    )

    factory_call = text.index(
        "build_production_prepare_application_service()",
        prepare_button,
    )

    assert (
        prepare_button
        < factory_call
    )

    guarded_region = text[
        prepare_button:
        factory_call
    ]

    assert (
        "prepare_requested"
        in guarded_region
    )

    assert (
        "preparation_service is None"
        in guarded_region
    )


def test_prepare_button_does_not_require_eager_service():
    text = source()

    render_start = text.index(
        "def render_job("
    )

    prepare_button = text.index(
        'prepare_requested = st.button(',
        render_start,
    )

    handle_call = text.index(
        "handle_prepare_application_action(",
        prepare_button,
    )

    button_block = text[
        prepare_button:
        handle_call
    ]

    assert (
        "disabled=preparation_service is None"
        not in button_block
    )


def test_injected_prepare_service_is_still_supported():
    text = source()

    render_start = text.index(
        "def render_job("
    )

    handle_call = text.index(
        "handle_prepare_application_action(",
        render_start,
    )

    render_block = text[
        render_start:
        handle_call
    ]

    assert (
        'st.session_state.get('
        in render_block
    )

    assert (
        '"_prepare_application_service"'
        in render_block
    )
