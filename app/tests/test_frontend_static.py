from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FRONTEND_MODULE_ORDER = [
    "constants.js",
    "state.js",
    "runtime.js",
    "utils.js",
    "persistence.js",
    "api.js",
    "providers.js",
    "nodes.js",
    "image-loader.js",
    "render-operation.js",
    "render-save.js",
    "render-history.js",
    "render-data-safety.js",
    "render-tag-management.js",
    "render-instance.js",
    "render-settings.js",
    "actions-settings.js",
    "tags.js",
    "actions-manager.js",
    "actions-data-safety.js",
    "actions-tag-management.js",
    "lightbox.js",
    "events.js",
]

CSS_MODULE_ORDER = [
    "00-variables.css",
    "01-base.css",
    "02-layout.css",
    "03-controls.css",
    "04-operation.css",
    "05-save-area.css",
    "06-instance-card.css",
    "07-image-slot.css",
    "08-settings.css",
    "09-history.css",
    "10-data-safety.css",
    "11-lightbox.css",
    "12-dialogs.css",
    "13-tag-management.css",
    "13-responsive.css",
]


def read_frontend_js_bundle() -> str:
    root = ROOT / "frontend"
    texts = [(root / "app.js").read_text(encoding="utf-8")]
    module_root = root / "js"
    seen = set()
    if module_root.exists():
        for name in FRONTEND_MODULE_ORDER:
            path = module_root / name
            if path.exists():
                texts.append(path.read_text(encoding="utf-8"))
                seen.add(path)
        for path in sorted(module_root.glob("*.js")):
            if path not in seen:
                texts.append(path.read_text(encoding="utf-8"))
    return "\n".join(texts)


def read_frontend_css_bundle() -> str:
    root = ROOT / "frontend"
    texts = [(root / "styles.css").read_text(encoding="utf-8")]
    module_root = root / "css"
    seen = set()
    if module_root.exists():
        for name in CSS_MODULE_ORDER:
            path = module_root / name
            if path.exists():
                texts.append(path.read_text(encoding="utf-8"))
                seen.add(path)
        for path in sorted(module_root.glob("*.css")):
            if path not in seen:
                texts.append(path.read_text(encoding="utf-8"))
    return "\n".join(texts)


def read_frontend(name: str) -> str:
    if name == "app.js":
        return read_frontend_js_bundle()
    if name == "styles.css":
        return read_frontend_css_bundle()
    return (ROOT / "frontend" / name).read_text(encoding="utf-8")


def read_frontend_raw(name: str) -> str:
    return (ROOT / "frontend" / name).read_text(encoding="utf-8")


def compact_css(text: str) -> str:
    return " ".join(text.split())


def test_v014_version_file_is_updated():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"


def test_editing_instance_still_has_delete_action():
    app_js = read_frontend("app.js")

    assert app_js.count('data-action="delete-instance"') >= 2


def test_path_replacement_dialog_is_connected_to_api():
    app_js = read_frontend("app.js")

    assert "path-replace-placeholder" not in app_js
    assert "openPathReplaceDialog" in app_js
    assert "/api/paths/replace/preview" in app_js
    assert "/api/paths/replace/apply" in app_js
    assert "确认替换数据库中的图片路径？" in app_js


def test_path_replacement_modal_styles_exist():
    css = read_frontend("styles.css")

    assert ".modal-backdrop" in css
    assert ".preview-box" in css


def test_manual_instance_creates_record_and_enters_edit_mode():
    app_js = read_frontend("app.js")

    assert "openManualInstanceDialog" not in app_js
    assert "manual-instance-dialog" not in app_js
    assert "async function createManualInstance()" in app_js
    assert 'prompt: "新实例"' in app_js
    assert "state.editing.set(Number(item.id), cloneInstanceForEdit(item));" in app_js


def test_manager_layout_uses_full_width_horizontal_record_rows():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert 'class="image-record record-row operation-area' in app_js
    assert 'class="image-record record-row instance-card"' in app_js
    assert ".panel {\n  width: 100%;" in css
    assert "width: min(920px, 100%);" not in css
    assert ".image-record {" in css
    assert ".operation-area.image-record {" in css
    assert ".instance-card.image-record {" in css
    assert ".record-detail" in css


def test_editing_state_does_not_add_instance_card_visual_style():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]
    assert "is-editing" not in instance_card
    assert ".instance-card.is-editing" not in css


def test_v001_image_slots_use_hover_overlay_and_lightbox():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "image-slot-filled" in app_js
    assert "slot-overlay" in app_js
    assert "data-image-path" in app_js
    assert "state.lightbox" in app_js
    assert "openImageLightbox" in app_js
    assert "renderLightbox" in app_js
    assert "window.open" not in app_js
    assert "event.stopPropagation();" in app_js
    assert ".image-slot-filled .slot-overlay" in css
    assert ".image-slot-filled:hover .slot-overlay" in css
    assert ".lightbox-backdrop" in css
    assert ".lightbox-image" in css


def test_v001_tag_and_path_use_placeholders_without_section_title():
    app_js = read_frontend("app.js")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")

    assert "<span>标签 / 路径</span>" not in app_js
    assert "<span>标签</span>" not in render_operation_js
    assert "<span>路径</span>" not in render_operation_js
    assert 'placeholder="添加标签"' in app_js
    assert 'placeholder="生成路径"' in app_js


def test_v001_border_tokens_are_darker():
    css = read_frontend("styles.css")

    assert "--line: #b8c0cc;" in css
    assert "--line-strong: #687386;" in css


def test_v001_operation_area_keeps_two_column_width_with_wider_input_images():
    css = read_frontend("styles.css")

    assert ".operation-area.image-record {\n  grid-column: 1 / -1;" in css
    assert ".operation-area .record-input-images" in css


def test_v002_operation_size_picker_and_payload_exist():
    app_js = read_frontend("app.js")

    assert "SIZE_MAP" in app_js
    assert "renderAspectRatioPicker" in app_js
    assert 'class="field record-aspect-ratio"' in app_js
    assert 'data-action="toggle-aspect-ratio-picker"' in app_js
    assert 'name="custom_generation_size"' in app_js
    assert "saveDefaultSize" in app_js
    assert "size: state.operation.generation_size" in app_js


def test_v002_settings_form_removes_default_size_field():
    app_js = read_frontend("app.js")

    assert "<span>default_size</span>" not in app_js
    assert 'name="default_size"' not in app_js
    assert "nextSettings.default_size = formData.get(\"default_size\")" not in app_js
    assert "default_size: formData.get(\"default_size\")" not in app_js


def test_v002_instance_size_renders_under_date():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "generation_size" in app_js
    assert "instance-size" in app_js
    assert ".instance-card-header .instance-size" in css


def test_v002_search_button_and_tag_dropdown_exist():
    app_js = read_frontend("app.js")

    assert 'data-action="apply-prompt-search"' in app_js
    assert 'data-action="apply-tag-filter"' not in app_js
    assert "renderTagFilterDropdown" in app_js
    assert 'name="tag_filter_search"' in app_js
    assert 'data-action="toggle-filter-tag"' in app_js
    tag_dropdown_fn = app_js[
        app_js.find("function renderTagFilterDropdown") :
        app_js.find("function renderModeFilterOptions")
    ]
    assert 'type="checkbox"' not in tag_dropdown_fn


def test_v002_lightbox_fit_and_drag_state_exist():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "panX" in app_js
    assert "panY" in app_js
    assert "isDragging" in app_js
    assert "startLightboxDrag" in app_js
    assert "moveLightboxDrag" in app_js
    assert "endLightboxDrag" in app_js
    assert "--lightbox-pan-x" in css
    assert "--lightbox-pan-y" in css
    assert "overflow: hidden;" in css[css.find(".lightbox-stage") : css.find(".lightbox-image")]


def test_v002_record_layout_and_image_rules_are_tightened():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "<h1>生图管理</h1>" not in app_js
    assert "--record-main-height: 88px;" in css
    assert "--bg: #eef2f6;" in css
    assert ".manager-panel" in css
    assert "text-overflow: ellipsis;" not in css[css.find(".instance-card-header time") : css.find(".image-grid")]
    assert "object-fit: cover;" in css
    assert "object-position: center center;" in css


def test_v003_settings_page_shows_raw_api_key_and_hides_global_defaults():
    app_js = read_frontend("app.js")

    assert "API_KEY_CLEAR_SENTINEL" not in app_js
    assert 'name="clear_api_key"' not in app_js
    assert "清除 API Key" not in app_js
    assert 'name="api_key" type="password"' not in app_js
    assert 'name="api_key"' in app_js
    assert "<span>default_output_dir</span>" not in app_js
    assert 'name="default_output_dir"' not in app_js[app_js.find("function renderSettings") : app_js.find("function cloneSettings")]
    assert "formData.get(\"default_output_dir\")" not in app_js


def test_v003_save_layout_preference_persists_and_bulk_adds_in_double_mode():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "saveLayoutClass" in app_js
    assert "saveLayoutPreference" in app_js
    assert "state.settings.save_layout" in app_js
    assert "/api/instances/bulk" in app_js
    assert "const createCount = currentSaveLayout() === \"double\" ? 2 : 1;" in app_js
    assert ".save-list.is-single" in css
    assert ".save-list.is-double" in css


def test_v003_operation_provider_prompt_clear_and_mode_specific_input_images():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "activeProviderDisplayName" in app_js
    assert "operation-provider-note" in app_js
    assert "shouldShowOperationInputImages" in app_js
    assert 'class="field record-input-images operation-input-images"' in app_js
    assert "clear-operation-prompt" in app_js
    assert ".search-prompt-clear" in css
    assert ".operation-area.mode-text_to_image" not in css


def test_v003_reusable_tag_selector_supports_existing_and_new_tags_inside_container():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "renderTagSelector" in app_js
    assert "tag-selector" in app_js
    assert "selectTagChoice" in app_js
    assert 'data-action="select-tag-option"' in app_js
    assert 'data-action="remove-tag-chip"' in app_js
    assert "新加：" in app_js
    assert ".tag-selector-input-wrap" in css
    assert ".tag-selector-menu" in css


def test_v003_prompt_overlay_date_split_and_footer_summary_exist():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "formatDateParts" in app_js
    assert "instance-date" in app_js
    assert "instance-time" in app_js
    assert "renderPromptField" in app_js
    assert "prompt-overlay" in app_js
    assert "save-toolbar-pagination" in app_js
    assert ".prompt-field:has(textarea:hover) .prompt-overlay" in css
    assert ".save-toolbar-pagination" in css


def test_v004_operation_uses_fixed_columns_and_always_visible_input_images():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "renderOperationInputImagesBlock" in app_js
    assert "operation-input-placeholder" not in app_js
    assert "输入图" in app_js
    assert ".operation-area .operation-prompt" in css
    assert ".operation-actions" in css
    assert ".operation-mode-block" in css
    assert "minmax(620px, 720px)" in css
    assert "minmax(360px, 1.25fr)" in css


def test_v004_save_area_removes_generation_path_and_keeps_provider_space():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    instance_card = app_js[app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")]
    assert "path-display" not in instance_card
    assert "displayPath" not in instance_card
    assert "instance-provider-note" in app_js
    assert ".instance-provider-note" in css


def test_v004_tag_filter_clear_and_per_page_options_exist():
    app_js = read_frontend("app.js")

    assert 'data-action="clear-tag-filter"' in app_js
    assert "clearTagFilter" in app_js
    assert 'renderSelectedOption("10", "10", String(state.filters.per_page))' in app_js
    assert 'renderSelectedOption("20", "20", String(state.filters.per_page))' in app_js


def test_v004_batch_save_boundaries_exist():
    app_js = read_frontend("app.js")

    assert "state.savingInstances" in app_js
    assert "batchSaveEditingInstances" in app_js
    assert "handleBatchSaveBoundary" in app_js
    assert "data-skip-batch-save" in app_js
    assert "excludeInstanceId" in app_js


def test_v004_lightbox_gallery_and_keyboard_navigation_exist():
    app_js = read_frontend("app.js")

    assert "gallery: []" in app_js
    assert "galleryIndex: 0" in app_js
    assert "openImageLightbox(path, sourceNode = null)" in app_js
    assert "buildOperationGallery" in app_js
    assert "buildInstanceGallery" in app_js
    assert "switchLightboxImage" in app_js
    assert 'data-action="lightbox-prev"' in app_js
    assert 'data-action="lightbox-next"' in app_js
    assert 'event.key === "ArrowLeft"' in app_js
    assert 'event.key === "ArrowRight"' in app_js


def test_v004_prompt_overlay_does_not_block_textarea_input():
    css = read_frontend("styles.css")

    assert ".prompt-overlay" in css
    prompt_overlay_css = css[css.find(".prompt-overlay") : css.find(".prompt-overlay:empty")]
    assert "pointer-events: none;" in prompt_overlay_css
    assert ".prompt-field.is-readonly:hover .prompt-overlay" in css


def test_v004_instance_input_images_have_clear_button():
    app_js = read_frontend("app.js")

    assert "renderImageFieldHeader" in app_js
    assert "clear-instance-input-images" in app_js
    assert "clearInstanceInputImages" in app_js


def test_v005_batch_save_skips_interactive_targets_and_defers_rendering():
    app_js = read_frontend("app.js")

    assert "function isInteractiveTarget(target)" in app_js
    interactive_fn = app_js[
        app_js.find("function isInteractiveTarget") : app_js.find("function shouldSkipBatchSave")
    ]
    assert "textarea, input, select, button" in interactive_fn
    assert "[data-skip-batch-save]" in interactive_fn
    assert "[data-lightbox-backdrop]" in interactive_fn
    assert "[data-path-replace-dialog]" in interactive_fn
    assert ".size-popover" in interactive_fn
    assert ".tag-selector-menu" in interactive_fn
    assert ".tag-filter-menu" in interactive_fn

    boundary_fn = app_js[
        app_js.find("function handleBatchSaveBoundary") : app_js.find("function applySaveFilters")
    ]
    assert "queueMicrotask" in boundary_fn or "setTimeout" in boundary_fn
    assert "await batchSaveEditingInstances" not in boundary_fn


def test_v067_batch_save_editing_instances_is_undoable_when_changed():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    batch_fn = actions_js[
        actions_js.find("async function batchSaveEditingInstances") :
        actions_js.find("function isInteractiveTarget")
    ]

    assert "hasInstanceDraftChanged" in batch_fn
    assert "createSessionSnapshot()" in batch_fn
    assert "state.undoStack" in batch_fn
    assert "state.redoStack = []" in batch_fn
    assert "changedIds" in batch_fn
    assert "undoableSavedCount" in batch_fn


def test_v005_prompt_input_updates_state_before_filter_or_layout_rerender():
    app_js = read_frontend("app.js")

    input_listener = app_js[
        app_js.find('app.addEventListener("input"') : app_js.find('document.addEventListener("keydown"')
    ]
    apply_filters = app_js[
        app_js.find("function applySaveFilters") : app_js.find("function clearTagFilter")
    ]
    set_layout = app_js[
        app_js.find("async function setSaveLayout") : app_js.find("function renderPathPreview")
    ]

    assert "state.operation.prompt = event.target.value || \"\";" in input_listener
    assert "syncInstanceDraftFromDom(card.dataset.id);" in input_listener
    assert "syncOperationFromDom();" in apply_filters
    assert "syncOperationFromDom();" in set_layout


def test_v005_operation_provider_stays_single_line_to_keep_path_baseline():
    css = (ROOT / "frontend" / "css" / "06-instance-card.css").read_text(encoding="utf-8")

    provider_start = css.find(".operation-provider-note")
    provider_css = css[
        provider_start : css.find(".operation-provider-select", provider_start)
    ]
    assert "white-space: nowrap;" in provider_css
    assert "text-overflow: ellipsis;" in provider_css


def test_v005_tag_clear_buttons_live_inside_their_own_boxes():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    filter_dropdown = app_js[
        app_js.find("function renderTagFilterDropdown") : app_js.find("function renderSaveArea")
    ]
    save_toolbar = app_js[
        app_js.find("function renderSaveArea") : app_js.find("function formatSource")
    ]
    tag_selector = app_js[
        app_js.find("function renderTagSelector") : app_js.find("function renderSizePicker")
    ]

    assert 'data-action="clear-tag-filter"' not in filter_dropdown
    assert 'class="filter-label-clear" data-action="clear-tag-filter"' in save_toolbar
    assert 'data-action="clear-tag-selector"' in tag_selector
    assert 'scope !== "instance"' in tag_selector
    assert "clearTagSelector" in app_js
    assert ".tag-selector-clear" in css
    assert ".tag-filter-clear" in css
    assert "position: absolute;" in css[css.find(".tag-selector-clear") : css.find(".tag-selector-menu")]


def test_v005_provider_source_row_and_manual_provider_editor_exist():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]
    header = instance_card[
        instance_card.find('class="record-meta instance-card-header"') : instance_card.find("renderPromptField")
    ]

    assert "sourceLabel(item.source)" not in header
    assert "renderProviderSourceRow" in app_js
    assert "source-badge" in app_js
    assert "manual-provider-input" in app_js
    assert "providerOptionsSelect" in app_js
    assert "<select name=\"instance_provider\"" in app_js
    assert 'name="instance_provider"' in app_js
    assert "source-badge" in css
    assert ".provider-source-row" in css


def test_v005_save_layout_uses_select_and_pagination_is_above_instances():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    save_area = app_js[
        app_js.find("function renderSaveArea") : app_js.find("function formatSource")
    ]
    batch_toolbar = app_js[
        app_js.find("function renderBatchToolbar") : app_js.find("function renderSaveArea")
    ]
    assert 'select name="save_layout"' in save_area
    assert 'data-action="set-save-layout"' not in save_area
    assert "layout-toggle" not in save_area
    assert batch_toolbar.count('class="save-toolbar-pagination"') == 1
    assert save_area.find("${renderBatchToolbar()}") < save_area.find('class="save-list')
    assert ".layout-toggle" not in css


def test_v005_operation_and_instance_backgrounds_are_distinct():
    css = read_frontend("styles.css")

    assert "--operation-bg: #f3f8ff;" in css
    assert "--instance-bg: #f7fbf4;" in css
    operation_css = css[css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")]
    instance_css = css[css.find(".instance-card.image-record") : css.find(".record-row textarea")]
    assert "background: var(--operation-bg);" in operation_css
    assert "background: var(--instance-bg);" in instance_css


def test_v005_operation_detail_bottom_aligns_and_text_mode_prompt_expands():
    css = read_frontend("styles.css")

    detail_css = css[css.find(".record-detail") : css.find(".operation-provider-note")]

    assert "min-height: calc(var(--record-main-height) + 20px);" in detail_css
    assert "grid-template-rows: auto 1fr auto;" in detail_css
    assert "--record-prompt-col: minmax(620px, 720px);" in css
    assert "--record-input-col: minmax(360px, 1.25fr);" in css
    assert ".operation-input-placeholder" not in css


def test_v006_prompt_editing_uses_real_textarea_and_composition_guard():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "function renderEditablePromptField" in app_js
    assert "function renderReadonlyPromptField" in app_js
    assert "function autoGrowPromptTextarea" in app_js
    assert "compositionstart" in app_js
    assert "compositionend" in app_js
    editable_fn = app_js[
        app_js.find("function renderEditablePromptField") : app_js.find("function renderReadonlyPromptField")
    ]
    assert "prompt-overlay" not in editable_fn
    input_listener = app_js[
        app_js.find('app.addEventListener("input"') : app_js.find('app.addEventListener("compositionstart"')
    ]
    assert "renderManager()" not in input_listener
    assert ".prompt-field.is-editable textarea:focus" in css
    assert ".prompt-field.is-readonly:hover .prompt-overlay" in css


def test_v006_operation_status_resolution_and_payload_exist():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "GENERATION_RESOLUTION_PRESETS" in app_js
    assert "DEFAULT_GENERATION_RESOLUTION" in app_js
    assert "renderResolutionPicker" in app_js
    assert "saveDefaultResolution" in app_js
    assert "activeGenerationResolution" in app_js
    assert "n: state.operation.generation_count" in app_js
    assert "default_resolution" in app_js
    assert "operation-status-row" in app_js
    assert "operation-button-row" in app_js
    assert ".operation-status-row" in css
    assert ".operation-button-row" in css


def test_v006_operation_layout_has_resolution_and_six_input_slots():
    css = read_frontend("styles.css")

    operation_css = css[
        css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")
    ]
    assert "var(--record-input-col)" in operation_css
    assert "--record-input-col: minmax(360px, 1.25fr);" in css
    assert ".operation-area .record-generation-options" in css
    assert ".operation-input-placeholder" not in css


def test_v006_tag_filter_renders_selected_chips_inside_control():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    tag_filter = app_js[
        app_js.find("function renderTagFilterDropdown") : app_js.find("function renderModeFilterOptions")
    ]
    assert "selectedTagChips" in tag_filter
    assert "tag-filter-chip" in tag_filter
    assert "已选" not in tag_filter
    assert ".tag-filter-chip" in css
    assert ".tag-filter-clear" in css


def test_v006_settings_can_manage_provider_instances():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "AVAILABLE_PROVIDER_ADAPTERS" in app_js
    assert "createProviderDraft" in app_js
    assert "deleteProvider" in app_js
    assert "data-action=\"new-provider\"" in app_js
    assert "data-action=\"delete-provider\"" in app_js
    assert 'name="provider_key"' in app_js
    assert 'name="adapter"' in app_js
    assert 'name="display_name"' in app_js
    assert ".provider-settings-grid" in css
    assert ".provider-settings-actions" in css


def test_v006_manual_provider_select_lists_all_providers():
    app_js = read_frontend("app.js")

    select_fn = app_js[
        app_js.find("function providerOptionsSelect") : app_js.find("function currentSaveLayout")
    ]
    assert "renderSelectedOption(\"\", \"未填写\"" in select_fn
    assert "for (const [name, provider] of sortedProviderEntries())" in select_fn
    assert "providerDisplayNameWithAdapter(name, provider)" in select_fn
    assert "providerOptionsDatalist" not in app_js


def test_v007_generation_options_share_one_operation_column():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "function renderGenerationOptions" in app_js
    operation_area = app_js[
        app_js.find("function renderOperationArea") : app_js.find("function renderTagFilterDropdown")
    ]
    assert "${renderGenerationOptions()}" in operation_area
    assert "${renderSizePicker()}" not in operation_area
    assert "${renderResolutionPicker()}" not in operation_area
    assert 'class="field record-generation-options"' in app_js
    assert ".record-generation-options" in css
    assert ".operation-area .record-generation-options { grid-column: 5; }" in css
    assert ".operation-area .record-detail { grid-column: 6 / 8; }" in css


def test_v007_text_and_image_modes_keep_same_prompt_and_placeholder_widths():
    css = read_frontend("styles.css")

    operation_css = css[
        css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")
    ]

    assert "grid-column: 2 / 4" not in operation_css
    assert ".operation-area.mode-text_to_image .operation-prompt" not in css
    assert ".operation-input-placeholder" not in css
    assert "var(--record-prompt-col)" in operation_css
    assert "var(--record-input-col)" in operation_css


def test_v007_prompt_focus_width_matches_prompt_column():
    css = read_frontend("styles.css")

    focus_css = css[
        css.find(".prompt-field.is-editable textarea:focus") : css.find(".prompt-overlay")
    ]
    assert "width: 100%;" in focus_css
    assert "620px" not in focus_css


def test_v007_generation_option_controls_are_compact():
    css = read_frontend("styles.css")

    size_css = css[css.find(".size-current") : css.find(".size-popover")]
    resolution_css = css[
        css.find(".resolution-current") : css.find(".size-current")
    ]

    assert "--operation-button-height:" in css
    assert "--operation-button-gap:" in css
    assert "--generation-option-height: var(--operation-button-height);" in css
    assert "height: var(--generation-option-height);" in size_css
    assert "height: var(--record-main-height)" not in size_css
    assert "height: var(--generation-option-height);" in resolution_css
    assert "height: var(--record-main-height)" not in resolution_css


def test_v008_operation_layout_has_button_and_status_columns():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    operation_area = app_js[
        app_js.find("function renderOperationArea") : app_js.find("function renderTagFilterDropdown")
    ]
    operation_css = css[
        css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")
    ]

    assert "var(--record-prompt-col)" in operation_css
    assert "var(--record-input-col)" in operation_css
    assert "var(--record-status-col)" in operation_css
    assert "--record-prompt-col: minmax(620px, 720px);" in css
    assert "--record-input-col: minmax(360px, 1.25fr);" in css
    assert "--record-status-col: 72px;" in css
    assert ".operation-area .operation-actions { grid-column: 8; }" in css
    status_panel_css = css[
        css.find(".operation-area .operation-status-panel") :
        css.find(".operation-area .operation-actions")
    ]
    assert "grid-column: 1;" in status_panel_css
    assert "grid-row: 1;" in status_panel_css
    assert 'class="operation-status-panel"' in operation_area
    assert 'class="message operation-status-row operation-status-tail"' in operation_area
    operation_actions = operation_area[
        operation_area.find('class="record-actions actions operation-actions"') : operation_area.find('class="operation-status-panel"')
    ]
    assert "data-message" not in operation_actions


def test_v008_operation_prompt_widens_and_input_column_can_compress():
    css = read_frontend("styles.css")

    operation_css = css[
        css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")
    ]
    focus_css = css[
        css.find(".prompt-field.is-editable textarea:focus") : css.find(".prompt-overlay")
    ]

    assert "var(--record-prompt-col)" in operation_css
    assert "var(--record-input-col)" in operation_css
    assert "--record-prompt-col: minmax(620px, 720px);" in css
    assert "--record-input-col: minmax(360px, 1.25fr);" in css
    assert "width: 100%;" in focus_css
    assert "620px" not in focus_css


def test_v008_resolution_uses_button_popover_without_cancel():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    clarity_fn = app_js[
        app_js.find("function renderClarityPicker") : app_js.find("function renderResolutionPicker")
    ]

    assert 'select name="generation_resolution"' not in clarity_fn
    assert "toggle-clarity-picker" in clarity_fn
    assert "set-generation-clarity" in clarity_fn
    assert "clarity-popover" in clarity_fn
    assert "取消" not in clarity_fn
    assert "clarity_picker_open" in app_js
    assert "toggleClarityPicker" in app_js
    assert "setGenerationClarity" in app_js
    assert ".option-current" in css
    assert ".select-arrow" in css
    assert ".clarity-popover" in css


def test_v008_instance_prompt_copy_action_exists():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]

    assert 'copyAction: "copy-instance-prompt"' in instance_card
    assert "function copyInstancePrompt" in app_js
    assert "function fallbackCopyText" in app_js
    assert 'data-action="copy-instance-prompt"' in app_js
    assert ".field-title-row" in css
    assert ".field-title-action" in css


def test_v009_dropdowns_do_not_render_close_buttons():
    app_js = read_frontend("app.js")

    aspect_fn = app_js[
        app_js.find("function renderAspectRatioPicker") : app_js.find("function renderSizePicker")
    ]
    clarity_fn = app_js[
        app_js.find("function renderClarityPicker") : app_js.find("function renderResolutionPicker")
    ]

    assert "size-close" not in aspect_fn
    assert "close-size-picker" not in aspect_fn
    assert "关闭" not in aspect_fn
    assert "关闭" not in clarity_fn
    assert "取消" not in clarity_fn
    assert "aspect-ratio-popover" in aspect_fn
    assert "clarity-popover" in clarity_fn


def test_v009_prompt_textareas_disable_browser_spelling_marks():
    app_js = read_frontend("app.js")

    editable_prompt = app_js[
        app_js.find("function renderEditablePromptField") : app_js.find("function renderReadonlyPromptField")
    ]
    readonly_prompt = app_js[
        app_js.find("function renderReadonlyPromptField") : app_js.find("function renderPromptField")
    ]

    for prompt_fn in (editable_prompt, readonly_prompt):
        assert 'spellcheck="false"' in prompt_fn
        assert 'autocapitalize="off"' in prompt_fn
        assert 'autocomplete="off"' in prompt_fn
        assert 'autocorrect="off"' in prompt_fn


def test_v009_operation_input_images_can_be_cleared():
    app_js = read_frontend("app.js")

    operation_input_fn = app_js[
        app_js.find("function renderOperationInputImagesBlock") : app_js.find("function renderOperationArea")
    ]

    assert "clear-operation-input-images" in operation_input_fn
    assert 'buttonLabel: "清除"' in operation_input_fn
    assert "function clearOperationInputImages" in app_js
    assert 'action === "clear-operation-input-images"' in app_js
    assert "state.operation.input_image_paths = [];" in app_js


def test_v009_instance_input_clear_button_only_in_edit_mode():
    app_js = read_frontend("app.js")

    image_header_fn = app_js[
        app_js.find("function renderImageFieldHeader") : app_js.find("function renderProviderSourceRow")
    ]
    instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]

    assert "const button = editable && action" in image_header_fn
    assert "idAttr" in image_header_fn
    assert 'action: "clear-instance-input-images"' in instance_card
    assert 'buttonLabel: "清除"' in instance_card


def test_v009_operation_two_row_controls_share_alignment_variables():
    css = read_frontend("styles.css")

    mode_css = css[css.find(".mode-row") : css.find(".mode-button")]
    options_css = css[css.find(".record-generation-options") : css.find(".record-generation-options .field > span")]
    actions_css = css[css.find(".operation-button-row") : css.find(".instance-actions")]
    size_css = css[css.find(".size-current") : css.find(".size-popover")]
    resolution_css = css[css.find(".resolution-current") : css.find(".size-current")]

    assert "--operation-button-height:" in css
    assert "--operation-button-gap:" in css
    assert "--record-detail-top-row:" in css
    assert "--record-detail-gap:" in css
    assert "--operation-control-stack-height:" in css
    assert "gap: var(--operation-button-gap);" in mode_css
    assert "gap: var(--record-detail-gap);" in options_css
    assert "gap: var(--record-detail-gap);" in actions_css
    assert "var(--record-detail-top-row)" in options_css
    assert "var(--operation-control-stack-height)" in options_css
    assert "var(--operation-button-height)" in options_css
    assert "height: var(--generation-option-height);" in size_css
    assert "height: var(--generation-option-height);" in resolution_css


def test_v010_operation_columns_are_named_variables():
    css = read_frontend("styles.css")
    operation_css = css[
        css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")
    ]

    for token in [
        "--record-meta-col",
        "--record-prompt-col",
        "--record-input-col",
        "--record-size-col",
        "--record-output-col",
        "--record-detail-col",
        "--record-action-col",
        "--record-status-col",
        "--record-grid-gap",
    ]:
        assert token in css

    assert "var(--record-meta-col)" in operation_css
    assert "var(--record-prompt-col)" in operation_css
    assert "var(--record-input-col)" in operation_css
    assert "var(--record-size-col)" in operation_css
    assert "var(--record-output-col)" in operation_css
    assert "var(--record-detail-col)" in operation_css
    assert "var(--record-action-col)" in operation_css
    assert "var(--record-status-col)" in operation_css
    assert "gap: var(--record-grid-gap);" in operation_css


def test_v010_single_save_layout_reuses_operation_columns_with_expanded_regions():
    css = read_frontend("styles.css")
    single_grid_css = css[
        css.find(".save-list.is-single .instance-card.image-record") : css.find(".instance-card-placeholder")
    ]
    single_rules_css = css[
        css.find(".save-list.is-single .instance-card .instance-card-header") : css.find("@media (max-width: 1540px)")
    ]

    assert "var(--record-meta-col)" in single_grid_css
    assert "var(--record-prompt-col)" in single_grid_css
    assert "var(--record-input-col)" in single_grid_css
    assert "var(--record-size-col)" in single_grid_css
    assert "var(--record-output-col)" in single_grid_css
    assert "var(--record-detail-col)" in single_grid_css
    assert "var(--record-status-col)" in single_grid_css
    assert "var(--record-action-col)" in single_grid_css
    assert single_grid_css.find("var(--record-status-col)") < single_grid_css.find("var(--record-action-col)")

    assert ".save-list.is-single .instance-card .instance-prompt" in single_rules_css
    assert "grid-column: 2;" in single_rules_css
    assert ".save-list.is-single .instance-card .record-input-images" in single_rules_css
    assert "grid-column: 3 / 5;" in single_rules_css
    assert ".save-list.is-single .instance-card .record-output-image" in single_rules_css
    assert "grid-column: 5;" in single_rules_css
    assert ".save-list.is-single .instance-card .record-detail" in single_rules_css
    assert "grid-column: 6 / 8;" in single_rules_css
    assert ".save-list.is-single .instance-card .instance-actions" in single_rules_css
    assert "grid-column: 8;" in single_rules_css


def test_v010_double_save_layout_keeps_existing_compact_grid():
    css = read_frontend("styles.css")
    base_instance_css = css[
        css.find(".instance-card.image-record") : css.find(".record-row textarea")
    ]
    double_css = css[
        css.find(".save-list.is-double") : css.find(".save-list.is-single")
    ]

    assert "grid-template-columns: 78px minmax(0, 1.1fr) minmax(0, 1fr) 76px minmax(0, .85fr) 64px;" in base_instance_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in double_css


def test_v010_responsive_breakpoints_update_shared_operation_columns():
    css = read_frontend("styles.css")
    medium_css = css[css.find("@media (max-width: 1540px)") : css.find("@media (max-width: 1120px)")]
    narrow_css = css[css.find("@media (max-width: 1120px)") : css.find("@media (max-width: 1200px)")]

    for section in (medium_css, narrow_css):
        assert "--record-meta-col:" in section
        assert "--record-prompt-col:" in section
        assert "--record-input-col:" in section
        assert "--record-size-col:" in section
        assert "--record-output-col:" in section
        assert "--record-detail-col:" in section
        assert "--record-action-col:" in section
        assert "--record-status-col:" in section

    assert "grid-template-columns: 80px minmax(420px, 1.2fr)" not in medium_css
    assert "grid-template-columns: 70px minmax(250px, 1.1fr)" not in narrow_css


def test_v010_mobile_single_save_layout_collapses_specific_grid():
    css = read_frontend("styles.css")
    mobile_css = css[css.find("@media (max-width: 760px)") :]

    assert ".save-list.is-single .instance-card.image-record" in mobile_css
    assert "grid-template-columns: 1fr;" in mobile_css[
        mobile_css.find(".save-list.is-single .instance-card.image-record") :
        mobile_css.find(".operation-area .operation-mode-block")
    ]


def test_v011_size_map_and_ratio_labels_replace_fixed_size_presets():
    app_js = read_frontend("app.js")

    assert "const SIZE_MAP" in app_js
    assert '"16:9":' in app_js
    assert '"1K": "1536x864"' in app_js
    assert '"9:16":' in app_js
    assert '"4K": "2160x3840"' in app_js
    assert "function aspectRatioForSize" in app_js
    assert "function displaySizeLabel" in app_js
    assert "自定义" in app_js
    assert "GENERATION_SIZE_PRESETS" not in app_js


def test_v011_resolution_picker_supports_custom_mode_without_visible_label():
    app_js = read_frontend("app.js")

    assert 'const CLARITY_PRESETS = ["1K", "2K", "4K", "custom"]' in app_js
    assert "generation_clarity" in app_js
    assert "activeGenerationClarity" in app_js
    assert 'data-clarity="${escapeHtml(preset)}"' in app_js
    assert 'name="custom_resolution"' not in app_js[
        app_js.find("function renderClarityPicker") : app_js.find("function renderResolutionPicker")
    ]
    assert "state.operation.generation_clarity === \"custom\"" in app_js


def test_v011_generation_count_control_is_numeric_and_passed_to_payload():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "generation_count: 1" in app_js
    assert 'name="generation_count"' in app_js
    assert "normalizeGenerationCount" in app_js
    assert "n: state.operation.generation_count" in app_js
    assert "<span>数量</span>" not in app_js
    assert ".resolution-count-row" in css


def test_v012_aspect_ratio_button_only_shows_ratio_or_custom():
    app_js = read_frontend("app.js")

    aspect_fn = app_js[
        app_js.find("function renderAspectRatioPicker") : app_js.find("function renderClarityPicker")
    ]

    assert "const ASPECT_RATIO_PRESETS = Object.keys(SIZE_MAP)" in app_js
    assert "displayAspectRatioButtonText" in app_js
    assert "displayAspectRatioOption" in app_js
    assert "displayCustomSizeOption" in app_js
    assert 'class="field record-aspect-ratio"' in aspect_fn
    assert 'data-action="toggle-aspect-ratio-picker"' in aspect_fn
    assert 'data-action="set-aspect-ratio"' in aspect_fn
    assert 'data-action="set-custom-generation-size"' in aspect_fn
    assert "${escapeHtml(displayAspectRatioButtonText())}" in aspect_fn
    assert "${escapeHtml(displayAspectRatioOption(ratio, clarity))}" in aspect_fn
    assert "${escapeHtml(displayCustomSizeOption(size))}" in aspect_fn
    assert "${escapeHtml(displaySizeLabel(size, resolution))}" not in aspect_fn


def test_v012_clarity_dropdown_has_no_input_and_keeps_count_beside_it():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    clarity_fn = app_js[
        app_js.find("function renderClarityPicker") : app_js.find("function renderGenerationOptions")
    ]

    assert 'const CLARITY_PRESETS = ["1K", "2K", "4K", "custom"]' in app_js
    assert 'class="field record-clarity"' in clarity_fn
    assert 'class="clarity-count-row"' in clarity_fn
    assert 'data-action="toggle-clarity-picker"' in clarity_fn
    assert 'data-action="set-generation-clarity"' in clarity_fn
    assert 'name="generation_count"' in clarity_fn
    assert 'name="custom_resolution"' not in clarity_fn
    assert 'name="custom_generation_size"' not in clarity_fn
    assert ".clarity-count-row" in css
    assert ".record-clarity" in css


def test_v012_custom_generation_sizes_are_saved_and_deletable():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "custom_generation_sizes" in app_js
    assert "function customGenerationSizes" in app_js
    assert "function addCustomGenerationSize" in app_js
    assert "function removeCustomGenerationSize" in app_js
    assert 'data-action="remove-custom-generation-size"' in app_js
    assert 'class="custom-size-delete"' in app_js
    assert ".custom-size-delete" in css


def test_v012_aspect_ratio_popover_opens_below_two_option_rows():
    css = read_frontend("styles.css")

    aspect_popover_css = css[
        css.rfind(".aspect-ratio-popover {") : css.find(".custom-size-option")
    ]

    assert "top: calc((var(--generation-option-height) * 2) + var(--operation-button-gap) + 6px);" in aspect_popover_css


def test_v012_generation_payload_uses_actual_size_and_clarity():
    app_js = read_frontend("app.js")

    payload_fn = app_js[
        app_js.find("function operationPayload") : app_js.find("async function generateFromOperation")
    ]

    assert "function activeGenerationClarity" in app_js
    assert "const resolutionLevel = activeGenerationClarity();" in payload_fn
    assert "const activeOpenAIGoogle = isActiveOpenAIGoogleProvider();" in payload_fn
    assert "ratio: activeOpenAIGoogle ? \"\" : state.operation.aspect_ratio" in payload_fn
    assert "resolution_level: activeOpenAIGoogle ? \"\" : resolutionLevel" in payload_fn
    assert "size: activeOpenAIGoogle ? \"\" : state.operation.generation_size" in payload_fn
    assert "n: state.operation.generation_count" in payload_fn
    assert "resolution," not in payload_fn


def test_v013_settings_renames_adapter_to_interface_type_and_groups_provider_fields():
    app_js = read_frontend("app.js")

    settings_fn = app_js[
        app_js.find("function renderSettings") : app_js.find("function cloneSettings")
    ]

    assert "<span>adapter</span>" not in settings_fn
    assert "接口类型" in settings_fn
    assert "Provider 基础信息" not in settings_fn
    assert "连接信息" in settings_fn
    assert "OpenAI API 参数" in settings_fn
    assert "调用示例" in settings_fn
    assert 'name="adapter"' in settings_fn
    assert "const ADAPTER_CAPABILITIES" in app_js
    assert '"openai": {' in app_js
    assert 'label: "google"' in app_js
    assert 'label: "other"' in app_js


def test_v013_settings_openai_parameters_and_code_examples_exist():
    app_js = read_frontend("app.js")

    assert "renderOpenAIProviderSettings" in app_js
    assert "调用示例" in app_js
    assert "quality" in app_js
    assert "output_format" in app_js
    assert "output_compression" in app_js
    assert "background" in app_js
    assert "moderation" in app_js
    assert "openai_call_method" in app_js
    assert "client.responses.create" in app_js
    assert "Google adapter 尚未接入具体调用代码" in app_js
    assert "Other adapter 用于后续自定义接口" in app_js


def test_v013_provider_display_adds_adapter_short_marker_without_extra_manager_row():
    app_js = read_frontend("app.js")

    assert "providerAdapterMarker" in app_js
    assert "providerDisplayNameWithAdapter" in app_js
    assert '"openai": "(c)"' in app_js
    assert '"google": "(g)"' in app_js
    assert '"other": "(o)"' in app_js
    assert "generation_params" not in app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]


def test_v014_manager_title_version_path_title_and_save_layout_order():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    save_area = app_js[
        app_js.find("function renderSaveArea") : app_js.find("function formatSource")
    ]
    operation_area = app_js[
        app_js.find("function renderOperationArea") : app_js.find("function renderTagFilterDropdown")
    ]

    assert 'const APP_VERSION = "V0.71";' in app_js
    assert "renderAppVersionBadge" in app_js
    assert "app-version" in css
    assert 'title="${escapeHtml(state.operation.generation_path)}"' in operation_area
    assert save_area.find('renderSelectedOption("single", "单列", layout)') < save_area.find(
        'renderSelectedOption("double", "双列", layout)'
    )


def test_v014_hover_preview_is_separate_from_click_lightbox():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "hoverPreview" in app_js
    assert "showImageHoverPreview" in app_js
    assert "hideImageHoverPreview" in app_js
    assert "renderImageHoverPreview" in app_js
    assert "data-image-hover-preview" in app_js
    assert 'app.addEventListener("pointerover"' in app_js
    assert 'app.addEventListener("pointerout"' in app_js
    assert "hideImageHoverPreview();" in app_js[
        app_js.find("const imageSlot = event.target.closest(\"[data-image-path]\")") :
        app_js.find("const actionNode = event.target.closest(\"[data-action]\")")
    ]
    assert ".image-hover-preview" in css
    assert ".image-hover-preview img" in css


def test_v014_settings_header_interface_and_connection_are_compact():
    app_js = read_frontend("app.js")

    settings_fn = app_js[
        app_js.find("function renderSettings") : app_js.find("function cloneSettings")
    ]

    assert "settings-title-row" in settings_fn
    assert "settings-provider-select" in settings_fn
    assert "<span>provider</span>" not in settings_fn
    assert "section-title-row" in app_js
    assert "settings-section-control" in app_js
    assert "openai：使用 OpenAI" not in settings_fn
    assert "google：使用 Google" not in settings_fn
    assert "other：其他接口" not in settings_fn
    assert "如果填写 api_key，优先使用 api_key" not in settings_fn
    assert "填写 api_key 时优先使用 api_key" in settings_fn


def test_v014_openai_call_method_controls_dynamic_parameter_tables():
    app_js = read_frontend("app.js")

    openai_fn = app_js[
        app_js.find("function renderOpenAIProviderSettings") : app_js.find("function renderAdapterSpecificSettings")
    ]

    assert "OpenAI API 参数" in openai_fn
    assert "OpenAI Image API 参数" not in openai_fn
    assert "最简单调用代码示例" not in openai_fn
    assert 'name="openai_call_method"' in openai_fn
    assert 'renderSelectedOption("gpt-image-2", "gpt-image-2", callMethod)' in openai_fn
    assert 'renderSelectedOption("response", "response", callMethod)' in openai_fn
    assert "renderSoftwareParam(\"prompt\")" in openai_fn
    assert "renderSoftwareParam(\"size\")" in openai_fn
    assert "renderSoftwareParam(\"n\")" in openai_fn
    assert "client.images.generate" in openai_fn
    assert "client.responses.create" in openai_fn
    assert "gpt-image-1.5" in openai_fn
    assert "来自软件" in app_js
    assert "仅 jpeg / webp 有效" not in openai_fn


def test_v015_openai_params_add_example_mode_and_software_output_path():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    openai_fn = app_js[
        app_js.find("function renderOpenAIProviderSettings") : app_js.find("function renderAdapterSpecificSettings")
    ]

    assert 'name="openai_example_mode"' in openai_fn
    assert 'renderSelectedOption("text_to_image", "文生图", exampleMode)' in openai_fn
    assert 'renderSelectedOption("image_to_image", "图生图", exampleMode)' in openai_fn
    assert "renderSoftwareParam(\"保存路径\")" in openai_fn
    assert "renderSoftwareParam(\"image / input_images\")" in openai_fn
    assert "固定为 1" in openai_fn
    assert ".param-field input:disabled" in css
    assert ".generation-count-input:disabled" in css


def test_v015_operation_image_mode_disables_generation_count_without_saving_default():
    app_js = read_frontend("app.js")

    clarity_fn = app_js[
        app_js.find("function renderClarityPicker") : app_js.find("function renderResolutionPicker")
    ]
    change_listener = app_js[
        app_js.find('app.addEventListener("change"') : app_js.find('app.addEventListener("input"')
    ]
    operation_payload = app_js[
        app_js.find("function operationPayload") : app_js.find("async function generateFromOperation")
    ]

    assert "isImageToImageMode" in app_js
    assert "state.operation.text_generation_count" in app_js
    assert "const countDisabled = isImageToImageMode()" not in clarity_fn
    assert 'name="generation_count"' in clarity_fn
    assert "if (isImageToImageMode())" not in change_listener[
        change_listener.find('event.target.name === "generation_count"') :
        change_listener.find('event.target.name === "custom_resolution"')
    ]
    assert "saveDefaultCount" in change_listener
    assert "n: state.operation.generation_count" in operation_payload


def test_v015_code_examples_have_tabs_edit_save_copy_and_custom_warning():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")
    text_script = (ROOT.parent / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    image_script = (ROOT.parent / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")

    assert "renderCodeExampleTabs" in app_js
    assert "fixed-example" in app_js
    assert "custom-code" in app_js
    assert "当前自定义代码已启用，生成将使用自定义代码。" in app_js
    assert 'data-action="edit-code-example"' in app_js
    assert 'data-action="save-code-example"' in app_js
    assert 'data-action="cancel-code-example"' in app_js
    assert 'data-action="copy-code-example"' in app_js
    assert 'data-action="clear-custom-script"' in app_js
    assert "state.openaiScriptExamples.text_to_image" in app_js
    assert "state.openaiScriptExamples.image_to_image" in app_js
    assert "from urllib.request import Request" in text_script
    assert "from urllib.request import urlopen" in text_script
    assert "run_openai_request(request_options)" in image_script
    assert ".images.edit(**request_options)" in image_script
    assert "response 文生图示例待完善" in app_js
    assert ".custom-script-warning" in css
    assert ".code-example-tabs" in css


def test_v016_navigation_generation_status_and_history_page_exist():
    app_js = read_frontend("app.js")
    index_html = read_frontend("index.html")

    assert 'data-page="history"' in index_html
    assert "历史记录" in index_html
    assert "generationStatus" in app_js
    assert "renderHistoryPage" in app_js
    assert "loadGenerationHistory" in app_js
    assert "/api/generation-history" in app_js
    assert "generationStatus.inProgress" in app_js
    assert "生成中" in app_js


def test_v016_settings_top_actions_user_agent_and_code_header_layout():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    settings_fn = app_js[
        app_js.find("function renderSettings") : app_js.find("function cloneSettings")
    ]
    code_tabs_fn = app_js[
        app_js.find("function renderCodeExampleTabs") : app_js.find("function renderOpenAIProviderSettings")
    ]

    assert 'renderSettingHistoryInput("user_agent"' in settings_fn
    assert "settings-top-actions" in settings_fn
    assert settings_fn.find("settings-top-actions") < settings_fn.find("显示名称")
    assert "provider-settings-actions" not in settings_fn
    assert "固定示例" not in code_tabs_fn
    assert "调用示例" in code_tabs_fn
    assert "自定义代码" in code_tabs_fn
    assert "code-example-title-row" in code_tabs_fn
    assert "data-action=\"clear-custom-script\"" in app_js
    assert "readonly" in code_tabs_fn
    assert ".code-example-title-row" in css
    assert "white-space: pre-wrap;" in css
    assert "overflow-y: hidden;" in css


def test_v016_fixed_examples_and_user_agent_templates_are_updated():
    app_js = read_frontend("app.js")
    text_script = (ROOT.parent / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    image_script = (ROOT.parent / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")

    assert 'api("/api/openai-script-examples")' in app_js
    assert "from urllib.request import Request" in text_script
    assert "import shutil" in text_script
    assert 'client_options["default_headers"] = {"User-Agent": user_agent}' in text_script
    assert 'headers = {"User-Agent": user_agent} if user_agent else {}' in text_script
    assert "http_client_options(verify=False)" in text_script
    assert "from urllib.request import Request" in image_script
    assert ".images.edit(**request_options)" in image_script
    assert "urlretrieve" not in app_js[
        app_js.find("function defaultCodeExample") : app_js.find("function fixedCodeExample")
    ]


def test_v016_output_compression_linkage_and_disabled_rules_are_explicit():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    openai_fn = app_js[
        app_js.find("function renderOpenAIProviderSettings") : app_js.find("function renderAdapterSpecificSettings")
    ]
    change_listener = app_js[
        app_js.find('app.addEventListener("change"') : app_js.find('app.addEventListener("input"')
    ]

    assert 'const compressionDisabled = outputFormat === "png" ? "disabled" : "";' in openai_fn
    assert 'name="output_compression"' in openai_fn
    assert 'data-output-format-select' in openai_fn
    assert 'event.target.name === "output_format"' in change_listener
    assert ".param-field input:disabled" in css
    assert ".param-field select:disabled" in css


def test_v017_parallel_generation_tasks_replace_single_running_lock():
    app_js = read_frontend("app.js")
    operation_area = app_js[
        app_js.find("function renderOperationArea") : app_js.find("function renderTagFilterDropdown")
    ]
    generate_fn = app_js[
        app_js.find("async function generateFromOperation") : app_js.find("async function saveSettings")
    ]

    assert "generationTasks" in app_js
    assert "createGenerationTask" in app_js
    assert "generationTaskSummary" in app_js
    assert "生成中 ${running.length} 个" in app_js
    assert "已完成 ${success.length}" in app_js
    assert "失败 ${failed.length}" in app_js
    assert "state.generationStatus.inProgress" not in generate_fn
    assert "state.generationStatus.inProgress" not in operation_area
    assert "data-generation-task-id" in app_js


def test_v017_code_example_title_row_default_display_and_editing_state():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")
    code_tabs_fn = app_js[
        app_js.find("function renderCodeExampleTabs") : app_js.find("function renderOpenAIProviderSettings")
    ]

    assert "codeExampleRows" in app_js
    assert "code-example-title-row" in code_tabs_fn
    assert "fixedReadonly" not in code_tabs_fn
    assert "is-editing" in app_js
    assert "固定示例" not in code_tabs_fn
    assert "调用示例</button>" in code_tabs_fn
    assert "自定义代码</button>" in code_tabs_fn
    assert ".code-example-actions button.is-editing" in css
    assert "display: none;" not in css[css.find(".code-example-panel") : css.find(".code-example-editor")]
    assert "overflow-y: hidden;" in css


def test_v017_text_to_image_example_iterates_multiple_response_items():
    text_script = (ROOT.parent / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")

    assert "for index, item in enumerate(response_items(resp), start=1):" in text_script
    assert "item_output_path = indexed_output_path(output_path, index)" in text_script
    assert 'image_url = getattr(item, "url", None)' in text_script
    assert 'client_options["default_headers"] = {"User-Agent": user_agent}' in text_script
    assert "urlretrieve" not in text_script


def test_v017_settings_are_full_width_and_sections_have_distinct_background():
    css = read_frontend("styles.css")

    settings_css = css[css.find(".settings-form") : css.find(".settings-title-row")]
    section_css = css[css.find(".settings-section {") : css.find(".settings-section h2")]

    assert "width: 100%;" in settings_css
    assert "max-width: none;" in settings_css
    assert "background: #f8fafc;" in section_css


def test_v017_clipboard_original_path_and_drag_guidance_exist():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "clipboardImageTarget" in app_js
    assert "setClipboardImageTarget" in app_js
    assert "pasteClipboardImagePaths" in app_js
    assert "/api/clipboard/image-paths" in app_js
    assert "剪贴板中没有可用的本地图片路径" in app_js
    assert "拖拽无法读取原始路径" in app_js
    assert "data-clipboard-image-target" in app_js
    assert ".image-slot.is-clipboard-target" in css


def test_v018_assets_topbar_and_settings_compaction_are_explicit():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")
    index_html = read_frontend("index.html")
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")

    settings_fn = app_js[
        app_js.find("function renderSettings") : app_js.find("function cloneSettings")
    ]

    assert "/static/styles.css?v=V0.71" in index_html
    assert "/static/app.js?v=V0.71" in index_html
    topbar_css = css[css.find(".topbar") : css.find(".brand")]
    body_css = css[css.find("body {") : css.find("body.has-lightbox")]
    assert "--topbar-height: 52px;" in css
    assert "position: fixed;" in topbar_css
    assert "top: 0;" in topbar_css
    assert "left: 0;" in topbar_css
    assert "right: 0;" in topbar_css
    assert "height: var(--topbar-height);" in topbar_css
    assert "padding-top: var(--topbar-height);" in body_css
    assert "title AI Image Manager V0.71" in launcher
    assert "Close the old service and restart V0.71 in this CMD" in launcher
    assert "Provider 基础信息" not in settings_fn
    identity_grid = settings_fn[
        settings_fn.find("provider-identity-grid") :
        settings_fn.find('renderSettingSection("连接信息"')
    ]
    assert identity_grid.find("显示名称") < identity_grid.find("内部编号") < identity_grid.find("接口类型")
    assert settings_fn.count('name="adapter"') == 1
    assert "provider-identity-grid" in settings_fn
    assert "connection-settings-grid" in settings_fn


def test_v018_empty_image_slots_select_without_opening_file_dialog():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "renderEmptyImageSlot" in app_js
    assert 'data-action="select-empty-image-slot"' in app_js
    assert "image-slot-upload-button" in app_js
    assert ".image-slot-upload-button" in css
    assert "[data-clipboard-image-target]" in app_js[
        app_js.find("function isInteractiveTarget") : app_js.find("function shouldSkipBatchSave")
    ]
    assert 'if (action === "select-empty-image-slot")' in app_js


def test_v018_code_example_removes_outer_heading_but_keeps_toolbar_and_default_content():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    openai_fn = app_js[
        app_js.find("function renderOpenAIProviderSettings") : app_js.find("function renderAdapterSpecificSettings")
    ]
    code_tabs_fn = app_js[
        app_js.find("function renderCodeExampleTabs") : app_js.find("function renderOpenAIProviderSettings")
    ]

    assert 'renderSettingSection("调用示例"' not in openai_fn
    assert "code-example-section" in openai_fn
    assert "调用示例</button>" in code_tabs_fn
    assert "自定义代码</button>" in code_tabs_fn
    assert "customCodeHasContent" in code_tabs_fn
    assert "state.settingsCodeExample.customTabExplicit" in code_tabs_fn
    assert ".code-example-section" in css


def test_v019_history_page_uses_compact_toolbar_pagination_and_three_columns():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    history_record_fn = app_js[
        app_js.find("function renderHistoryRecord") : app_js.find("function renderHistoryPage")
    ]
    history_page_fn = app_js[
        app_js.find("function renderHistoryPage") : app_js.find("function renderSettingSection")
    ]

    assert "history-top-row" in history_page_fn
    assert "history-inline-toolbar" in history_page_fn
    assert "history-page-summary" in history_page_fn
    assert 'data-action="refresh-history"' in history_page_fn
    assert "筛选" in history_page_fn
    assert "总数" in history_page_fn
    assert "第 ${escapeHtml(currentPage)} / ${escapeHtml(totalPages)} 页" in history_page_fn

    assert "history-content-grid" in history_record_fn
    assert "history-prompt-cell" in history_record_fn
    assert "history-json-cell" in history_record_fn
    assert "history-small-cell" in history_record_fn
    assert "history-output-paths" in history_record_fn
    assert "输入图片路径" not in history_record_fn
    assert "输出图片路径" not in history_record_fn
    assert "参数 JSON</span>" not in history_record_fn
    assert "提示词</span>" not in history_record_fn

    grid_css = css[css.find(".history-content-grid") : css.find(".history-text-box")]
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 2fr);" in grid_css
    assert "overflow-wrap: anywhere;" in css[css.find(".history-small-cell") : css.find(".history-output-paths")]


def test_v019_history_long_text_popovers_are_selectable_and_click_pinned():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "toggleHistoryTextPopover" in app_js
    assert "closeHistoryTextPopover" in app_js
    assert "data-history-popover-source" in app_js
    assert "data-history-popover-kind" in app_js
    assert "history-popover is-pinned" in app_js
    assert "history-popover-content" in app_js
    popover_css = css[css.find(".history-popover") : css.find(".check-row")]
    assert "user-select: text;" in popover_css
    assert "white-space: pre-wrap;" in popover_css


def test_v019_code_examples_are_visible_and_editable_without_hidden_panels():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    code_tabs_fn = app_js[
        app_js.find("function renderCodeExampleTabs") : app_js.find("function renderOpenAIProviderSettings")
    ]
    show_tab_fn = app_js[
        app_js.find("function showCodeExampleTab") : app_js.find("function editCodeExample")
    ]
    input_listener = app_js[
        app_js.find('app.addEventListener("input"') : app_js.find('app.addEventListener("focusin"')
    ]

    assert "fixedReadonly" not in code_tabs_fn
    assert "readonly" in code_tabs_fn
    assert "displayCodeTab" in code_tabs_fn
    assert 'class="is-editing"' in app_js
    assert 'name="fixed_code_example"' in code_tabs_fn
    assert 'name="custom_script"' in code_tabs_fn
    assert "state.settingsCodeExample.editing = false" not in show_tab_fn
    assert 'event.target.name === "fixed_code_example"' not in input_listener
    assert "state.settingsCodeExample.editing" not in input_listener
    assert "display: none;" not in css[css.find(".code-example-panel") : css.find(".code-example-editor")]


def test_v020_code_example_textareas_disable_browser_spellcheck():
    app_js = read_frontend("app.js")
    code_tabs_fn = app_js[
        app_js.find("function renderCodeExampleTabs") : app_js.find("function renderOpenAIProviderSettings")
    ]

    assert 'name="fixed_code_example"' in code_tabs_fn
    assert 'name="custom_script"' in code_tabs_fn
    assert code_tabs_fn.count('spellcheck="false"') >= 2
    assert code_tabs_fn.count('autocapitalize="off"') >= 2
    assert code_tabs_fn.count('autocomplete="off"') >= 2
    assert code_tabs_fn.count('autocorrect="off"') >= 2


def test_v020_operation_provider_dropdown_uses_settings_options_and_saves_default():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    operation_fn = app_js[
        app_js.find("function renderOperationArea") : app_js.find("function historyStatusLabel")
    ]
    change_listener = app_js[
        app_js.find('app.addEventListener("change"') : app_js.find('app.addEventListener("input"')
    ]

    assert "renderOperationProviderSelect" in app_js
    assert "renderOperationProviderSelect()" in operation_fn
    assert "toggle-operation-provider-dropdown" in app_js
    assert "select-operation-provider" in app_js
    assert "activeProviderName()" in app_js
    assert "providerDisplayName(providerName)" in app_js
    assert "changeOperationProvider" in app_js
    assert 'event.target.name === "operation_provider"' not in change_listener
    assert "changeOperationProvider(providerKey)" in app_js
    assert "api(\"/api/settings\"" in app_js
    assert "已切换 Provider" in app_js
    assert ".operation-provider-select" in css


def test_v020_history_toolbar_keeps_pagination_in_same_top_row():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    history_page_fn = app_js[
        app_js.find("function renderHistoryPage") : app_js.find("function closeHistoryTextPopover")
    ]

    assert "history-top-row" in history_page_fn
    assert "history-right-tools" in history_page_fn
    assert "history-page-summary" in history_page_fn
    assert "筛选</button>" not in history_page_fn
    assert history_page_fn.find("刷新") < history_page_fn.find("history-page-summary")
    assert "history-pagination-row" not in history_page_fn
    assert "save-footer history-footer" not in history_page_fn
    assert "history-right-tools" in css
    assert "margin-left: auto;" in css[css.find(".history-right-tools") : css.find(".history-list")]


def test_v021_settings_provider_selector_is_edit_scope_only():
    app_js = read_frontend("app.js")

    render_settings_fn = app_js[
        app_js.find("function renderSettings") : app_js.find("function cloneSettings")
    ]
    settings_change_block = app_js[
        app_js.find('if (event.target.name === "provider")') :
        app_js.find('if (\n    event.target.name === "adapter"')
    ]
    save_settings_fn = app_js[
        app_js.find("async function saveSettings") : app_js.find("async function changeOperationProvider")
    ]
    sync_draft_fn = app_js[
        app_js.find("function syncSettingsProviderDraftFromForm") : app_js.find("async function loadInstances")
    ]

    assert "settingsEditingProvider" in app_js
    assert "settingsEditingProviderName" in app_js
    assert "const providerName = settingsEditingProviderName();" in render_settings_fn
    assert "state.settingsEditingProvider = event.target.value;" in settings_change_block
    assert "state.settings.active_provider" not in settings_change_block
    assert "nextSettings.active_provider = providerKey;" not in save_settings_fn
    assert "state.settings.active_provider = providerKey;" not in sync_draft_fn


def test_v021_new_and_delete_provider_do_not_change_operation_provider():
    app_js = read_frontend("app.js")

    create_provider_fn = app_js[
        app_js.find("function createProviderDraft") : app_js.find("async function deleteProvider")
    ]
    delete_provider_fn = app_js[
        app_js.find("async function deleteProvider") : app_js.find("function currentSettingsForm")
    ]

    assert "state.settingsEditingProvider = key;" in create_provider_fn
    assert "nextSettings.active_provider = key;" not in create_provider_fn
    assert "const providerName = settingsEditingProviderName();" in delete_provider_fn
    assert "providerName === activeProviderName()" in delete_provider_fn
    assert "当前 Provider 正在操作区使用，请先到生图管理页切换 Provider 后再删除。" in delete_provider_fn
    assert "!Object.prototype.hasOwnProperty.call(nextSettings.providers, nextSettings.active_provider)" in delete_provider_fn


def test_v021_ctrl_enter_triggers_manager_generation_with_guards():
    app_js = read_frontend("app.js")

    keydown_fn = app_js[
        app_js.find('document.addEventListener("keydown"') :
        app_js.find('document.addEventListener("paste"')
    ]

    assert "function canUseCtrlEnterGenerate(event)" in app_js
    assert "event.ctrlKey" in app_js
    assert 'event.key === "Enter"' in app_js
    assert "event.repeat" in app_js
    assert "event.isComposing" in app_js
    assert "state.isComposingPrompt" in app_js
    assert 'state.page !== "manager"' in app_js
    assert "state.lightbox.path" in app_js
    assert "canUseCtrlEnterGenerate(event)" in keydown_fn
    assert "event.preventDefault();" in keydown_fn
    assert "submitSelectedInstances();" in keydown_fn


def test_v022_ui_state_persistence_helpers_exist_and_exclude_editing_instances():
    app_js = read_frontend("app.js")
    persistence_block = app_js[
        app_js.find("function defaultPersistedUiState") : app_js.find("function maxPageForTotal")
    ]

    assert 'const UI_STATE_STORAGE_KEY = "AIImageManager.uiState.v1";' in app_js
    assert "function defaultPersistedUiState()" in app_js
    assert "function loadPersistedUiState()" in app_js
    assert "function persistUiState()" in app_js
    assert "function applyPersistedUiState(savedState)" in app_js
    assert "function persistedOperationState()" in app_js
    assert "function persistedSaveFilterState()" in app_js
    assert "function persistedHistoryState()" in app_js
    assert "localStorage.getItem(UI_STATE_STORAGE_KEY)" in app_js
    assert "localStorage.setItem(UI_STATE_STORAGE_KEY" in app_js
    assert "state.operation.prompt" in persistence_block
    assert "state.filters.per_page" in persistence_block
    assert "state.history.per_page" in persistence_block
    assert "state.editing" not in persistence_block
    assert "state.savingInstances" not in persistence_block
    assert "generationTasks" not in persistence_block


def test_v022_boot_applies_persisted_ui_state_before_loading_lists():
    app_js = read_frontend("app.js")
    boot_start = app_js.find("async function boot")
    boot_fn = app_js[boot_start : app_js.find("tabs.forEach", boot_start)]

    assert "const persistedUiState = loadPersistedUiState();" in boot_fn
    assert "applyPersistedUiState(persistedUiState);" in boot_fn
    assert boot_fn.find("applyPersistedUiState(persistedUiState);") < boot_fn.find("await loadInstances();")
    assert boot_fn.find("applyPersistedUiState(persistedUiState);") < boot_fn.find("await loadTags();")


def test_v022_save_and_history_filter_changes_persist_ui_state():
    app_js = read_frontend("app.js")
    apply_save_filters = app_js[
        app_js.find("function applySaveFilters") : app_js.find("function applyHistoryFilters")
    ]
    apply_history_filters = app_js[
        app_js.find("function applyHistoryFilters") : app_js.find("function changeHistoryPage")
    ]
    change_save_page = app_js[
        app_js.find("function changeSavePage") : app_js.find("async function setSaveLayout")
    ]
    change_history_page = app_js[
        app_js.find("function changeHistoryPage") : app_js.find("function clearTagFilter")
    ]
    clear_tag_filter = app_js[
        app_js.find("function clearTagFilter") : app_js.find("function startEditingInstance")
    ]

    assert "persistUiState();" in apply_save_filters
    assert "state.filters.per_page = normalizeSavePerPage" in apply_save_filters
    assert "persistUiState();" in apply_history_filters
    assert "state.history.per_page = normalizeHistoryPerPage" in apply_history_filters
    assert "persistUiState();" in change_save_page
    assert "persistUiState();" in change_history_page
    assert "persistUiState();" in clear_tag_filter


def test_v022_operation_draft_changes_and_beforeunload_persist_ui_state():
    app_js = read_frontend("app.js")
    click_listener = app_js[
        app_js.find('app.addEventListener("click"') : app_js.find('app.addEventListener("change"')
    ]
    input_listener = app_js[
        app_js.find('app.addEventListener("input"') : app_js.find('app.addEventListener("focusin"')
    ]
    beforeunload_listener = app_js[
        app_js.find('window.addEventListener("beforeunload"') : app_js.find('document.addEventListener("keydown"')
    ]

    assert "persistUiState();" in input_listener[input_listener.find('event.target.name === "prompt"') :]
    assert "persistUiState();" in input_listener[input_listener.find('event.target.name === "generation_count"') :]
    assert 'action === "set-operation-mode"' not in click_listener
    assert "persistUiState();" in click_listener[click_listener.find('action === "clear-operation"') :]
    assert 'window.addEventListener("beforeunload"' in app_js
    assert "syncOperationFromDom();" in beforeunload_listener
    assert "persistUiState();" in beforeunload_listener


def test_v022_pagination_protection_reloads_invalid_pages_for_save_and_history():
    app_js = read_frontend("app.js")
    load_instances = app_js[
        app_js.find("async function loadInstances") : app_js.find("async function loadTags")
    ]
    load_history = app_js[
        app_js.find("async function loadGenerationHistory") : app_js.find("function instanceById")
    ]

    assert "function maxPageForTotal(total, perPage)" in app_js
    assert "function normalizePageForTotal(page, total, perPage)" in app_js
    assert "function shouldReloadForNormalizedPage(currentPage, normalizedPage)" in app_js
    assert "const normalizedPage = normalizePageForTotal(" in load_instances
    assert "shouldReloadForNormalizedPage(requestedPage, normalizedPage)" in load_instances
    assert "return loadInstances();" in load_instances
    assert "const normalizedPage = normalizePageForTotal(" in load_history
    assert "shouldReloadForNormalizedPage(requestedPage, normalizedPage)" in load_history
    assert "return loadGenerationHistory();" in load_history


def test_v023_data_safety_page_and_resubmit_entry_points_exist():
    app_js = read_frontend("app.js")
    index_html = read_frontend("index.html")

    assert 'data-page="data-safety"' in index_html
    assert "renderDataSafetyPage" in app_js
    assert "立即备份" in app_js
    assert "导出数据" in app_js
    assert "恢复当前文件" in app_js
    assert "打开备份文件夹" in app_js
    assert "重提" in app_js
    assert "async function resubmitInstance" in app_js
    assert "record.id" in app_js
    assert "instance_number" in app_js
    assert "displayNumber" in app_js
    assert "String(index + 1).padStart(3, \"0\")" not in app_js[app_js.find("function renderHistoryRecord"):app_js.find("function renderInstanceCard")]
    assert "createBackup" in app_js
    assert "loadBackups" in app_js
    assert "restoreSelectedBackup" in app_js
    assert "/api/backups" in app_js
    assert "/api/exports" in app_js
    assert "/api/exports/tasks/" in app_js
    assert "/api/restore" in app_js
    assert "pre_restore" in app_js
    assert "恢复前会自动备份当前数据" in app_js


def test_v024_frontend_uses_native_modules_and_expected_files_exist():
    index_html = read_frontend("index.html")
    raw_app_js = read_frontend_raw("app.js")
    module_root = ROOT / "frontend" / "js"

    assert '<script type="module" src="/static/app.js?v=V0.71"></script>' in index_html
    assert module_root.is_dir()
    for name in FRONTEND_MODULE_ORDER:
        assert (module_root / name).is_file(), name
    assert 'import "./js/constants.js";' in raw_app_js
    assert "registerRuntime" in raw_app_js
    assert len(raw_app_js.splitlines()) < 260


def test_v024_pending_instances_and_resubmit_delete_inline_actions_exist():
    app_js = read_frontend("app.js")

    assert "pendingInstances" in app_js
    assert "createPendingInstancesForTask" in app_js
    assert "removePendingInstancesForTask" in app_js
    assert "pending_label: \"生成中\"" not in app_js
    assert "started_at_ms" in app_js
    assert "formatPendingElapsed" in app_js
    assert "item.pending" in app_js
    assert "instance-inline-actions" in app_js
    assert "resubmit-instance" in app_js
    assert "delete-instance" in app_js


def test_v024_save_and_history_have_first_last_pagination_actions():
    app_js = read_frontend("app.js")

    assert 'data-action="save-page-first"' in app_js
    assert 'data-action="save-page-last"' in app_js
    assert 'data-action="history-page-first"' in app_js
    assert 'data-action="history-page-last"' in app_js
    assert "function setSavePage(page)" in app_js
    assert "function setHistoryPage(page)" in app_js


def test_v025_css_uses_import_entry_and_expected_module_files_exist():
    index_html = read_frontend("index.html")
    raw_styles = read_frontend_raw("styles.css")
    css_root = ROOT / "frontend" / "css"

    assert '<link rel="stylesheet" href="/static/styles.css?v=V0.71">' in index_html
    assert "frontend/css" not in index_html
    assert css_root.is_dir()
    for name in CSS_MODULE_ORDER:
        assert (css_root / name).is_file(), name
        assert f'@import url("./css/{name}");' in raw_styles
    assert raw_styles.strip().startswith('@import url("./css/00-variables.css");')
    assert raw_styles.strip().endswith('@import url("./css/13-responsive.css");')


def test_v025_design_variables_are_centralized():
    variables_path = ROOT / "frontend" / "css" / "00-variables.css"
    responsive_path = ROOT / "frontend" / "css" / "13-responsive.css"

    assert variables_path.is_file()
    assert responsive_path.is_file()
    variables_css = variables_path.read_text(encoding="utf-8")
    responsive_css = responsive_path.read_text(encoding="utf-8")

    for token in [
        "--control-height:",
        "--button-height:",
        "--input-height:",
        "--image-slot-width:",
        "--image-slot-height:",
        "--border-color:",
        "--border-strong:",
        "--page-bg:",
        "--operation-bg:",
        "--instance-bg:",
        "--hover-bg:",
        "--font-size-base:",
        "--space-8:",
    ]:
        assert token in variables_css
    assert "@media" in responsive_css


def test_v025_no_horizontal_overflow_guard_and_data_safety_buttons_use_control_tokens():
    css = read_frontend("styles.css")

    assert "overflow-x: hidden;" in css
    assert "--button-height" in css
    assert "--control-radius" in css
    data_safety_css = css[css.find(".data-safety") : css.find(".backup-list")]
    assert "var(--button-height)" in data_safety_css
    assert "var(--control-radius)" in data_safety_css


def test_v025_pending_instances_are_separate_from_real_pagination():
    app_js = read_frontend("app.js")
    render_save_area = app_js[
        app_js.find("function renderSaveArea") : app_js.find("Object.assign(globalThis", app_js.find("function renderSaveArea"))
    ]

    assert "const pendingInstances = state.pendingInstances || [];" in render_save_area
    assert "const realInstances = state.instances || [];" in render_save_area
    assert "const processInstances = renderPendingProcessInstances(pendingInstances);" in render_save_area
    assert "processCards = processInstances.map" in render_save_area
    assert "const cards = formalInstances.map" in render_save_area
    assert "pending-section" in render_save_area
    assert "state.total" in render_save_area


def test_v025_resubmit_and_delete_live_in_separate_action_regions():
    app_js = read_frontend("app.js")
    render_instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]
    inline_actions = render_instance_card[
        render_instance_card.find("const inlineActions") : render_instance_card.find("return `")
    ]
    record_actions = render_instance_card[
        render_instance_card.find('class="record-actions instance-actions"') :
        render_instance_card.find("</article>")
    ]

    assert "copy-submit-instance" in render_instance_card
    assert "submitAction" in inline_actions
    assert "retry-failed-instance" in inline_actions
    assert "delete-instance" not in inline_actions
    assert "edit-instance" in record_actions
    assert "delete-instance" in record_actions


def test_v026_provider_capabilities_are_centralized_in_provider_module():
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    constants_js = (ROOT / "frontend" / "js" / "constants.js").read_text(encoding="utf-8")
    app_js = read_frontend("app.js")

    assert "const ADAPTER_CAPABILITIES" in providers_js
    assert "const PROVIDER_ADAPTER_MARKERS" in providers_js
    assert "const AVAILABLE_PROVIDER_ADAPTERS" in providers_js
    assert "PROVIDER_ADAPTER_MARKERS" not in constants_js
    assert "AVAILABLE_PROVIDER_ADAPTERS" not in constants_js
    assert "function normalizeProviderAdapter" in providers_js
    assert "function providerCapability" in providers_js
    assert "function providerCallMethodCapability" in providers_js
    assert "function isProviderImplemented" in providers_js
    assert "function providerUnavailableMessage" in providers_js
    assert '"google": {' in providers_js
    assert 'message: "Google adapter 暂未实现。"' in providers_js
    assert '"other": {' in providers_js
    assert 'message: "Other adapter 暂未实现。"' in providers_js
    assert "supportsImageToImage: false" in providers_js

    adapter_settings_start = app_js.find("function renderAdapterSpecificSettings")
    adapter_settings_fn = app_js[
        adapter_settings_start :
        app_js.find("function renderSettings", adapter_settings_start)
    ]
    assert "const capability = providerCapability(provider);" in adapter_settings_fn
    assert "provider.adapter === \"google\"" not in adapter_settings_fn
    assert "provider.adapter === \"other\"" not in adapter_settings_fn
    assert "providerUnavailableMessage(provider)" in adapter_settings_fn


def test_v026_history_snapshot_display_uses_defensive_provider_params():
    app_js = read_frontend("app.js")

    history_record_fn = app_js[
        app_js.find("function renderHistoryRecord") :
        app_js.find("function renderHistoryPage")
    ]
    assert "record.params || {}" in history_record_fn
    assert "params.provider_key || record.provider_key" in history_record_fn
    assert "params.adapter || record.adapter" in history_record_fn
    assert "params.openai_call_method || record.openai_call_method" in history_record_fn


def test_v027_save_toolbar_immediate_filters_batch_controls_and_lazy_images_exist():
    app_js = read_frontend("app.js")

    assert "SAVE_MODE_FILTER_OPTIONS" in app_js
    assert "mode_filter" in app_js
    assert 'params.set("mode_filter"' in app_js
    assert "__untagged__" in app_js
    assert '"无"' in app_js
    assert 'data-action="apply-tag-filter"' not in app_js
    assert 'data-action="select-current-page"' in app_js
    assert 'data-action="clear-selection"' in app_js
    assert 'data-action="batch-add-tags"' in app_js
    assert 'data-action="batch-delete-instances"' in app_js
    assert "/api/instances/batch/tags/add" in app_js
    assert "/api/instances/batch/tags/remove" in app_js
    assert "/api/instances/batch/delete" in app_js
    assert 'loading="lazy"' in app_js
    assert 'decoding="async"' in app_js
    assert "路径批量替换" not in app_js
    assert "路径替换" in app_js
    assert "新增实例" not in app_js
    assert ">新增<" in app_js


def test_v066_batch_toolbar_replaces_remove_tags_with_submit_and_copy():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    batch_toolbar = render_save_js[
        render_save_js.find("function renderBatchToolbar") :
        render_save_js.find("function renderInstanceThumbnailTile")
    ]

    assert 'data-action="batch-remove-tags"' not in batch_toolbar
    assert 'data-action="batch-submit-instances"' in batch_toolbar
    assert 'data-action="batch-copy-instances"' in batch_toolbar
    assert batch_toolbar.find('data-action="batch-delete-instances"') < batch_toolbar.find('data-action="batch-submit-instances"')
    assert batch_toolbar.find('data-action="batch-submit-instances"') < batch_toolbar.find('data-action="batch-copy-instances"')
    assert batch_toolbar.find('data-action="batch-copy-instances"') < batch_toolbar.find('data-action="toggle-thumbnail-view"')
    assert 'data-action="batch-submit-instances" ${disabled}>提交</button>' in batch_toolbar
    assert 'data-action="batch-copy-instances" ${disabled}>复制</button>' in batch_toolbar
    assert 'if (action === "batch-submit-instances")' in events_js
    assert "submitSelectedInstances();" in events_js[
        events_js.find('if (action === "batch-submit-instances")') :
        events_js.find('if (action === "batch-copy-instances")')
    ]
    assert 'if (action === "batch-copy-instances")' in events_js
    assert "batchCopyInstances();" in events_js
    assert "async function batchCopyInstances" in actions_js


def test_v066_batch_copy_creates_prepared_instances_and_is_undoable():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    batch_copy_fn = actions_js[
        actions_js.find("function copyInstanceToPreparedPayload") :
        actions_js.find("function formatPendingTimerText")
    ]
    batch_action_fn = actions_js[
        actions_js.find("async function batchCopyInstances") :
        actions_js.find("function formatPendingTimerText")
    ]

    assert 'runUndoableAction("批量复制实例"' in batch_action_fn
    assert 'api("/api/instances/bulk"' in batch_action_fn
    assert "copyInstanceToPreparedPayload" in batch_copy_fn
    assert "generation_status" in batch_copy_fn
    assert '"ready"' in batch_copy_fn
    assert "output_image_path" in batch_copy_fn
    assert "generation_error" in batch_copy_fn
    assert "generation_task_id" in batch_copy_fn
    assert "input_image_paths" in batch_copy_fn
    assert "generation_params" in batch_copy_fn
    assert "clearCurrentPageSelection();" in batch_action_fn


def test_v067_save_status_filter_is_multiselect_ordered_and_persisted():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis")
    ]
    status_dropdown = render_save_js[
        render_save_js.find("function renderSaveStatusFilterDropdown") :
        render_save_js.find("function saveStatusFilterLabel")
    ]

    assert "statuses: []" in state_js[state_js.find("filters:") : state_js.find("instances:")]
    assert "renderSaveStatusFilterDropdown()" in save_area
    assert 'select name="status"' not in save_area
    assert 'name="status"' in save_area
    assert 'data-action="toggle-save-status-filter-dropdown"' in status_dropdown
    assert 'data-action="toggle-save-status-filter"' in status_dropdown
    expected_order = [
        'value: "all"',
        'value: "running"',
        'value: "prepared"',
        'value: "failed"',
        'value: "generated"',
        'value: "other"',
    ]
    positions = [status_dropdown.find(token) for token in expected_order]
    assert all(position >= 0 for position in positions)
    assert positions == sorted(positions)
    assert 'params.append("statuses", status);' in actions_data_js
    assert 'params.set("status", state.filters.status || "all");' not in actions_data_js
    assert "toggleSaveStatusFilter" in actions_js
    assert 'action === "toggle-save-status-filter"' in events_js
    assert "normalizeSavedStatuses" in persistence_js


def test_v067_instance_card_uses_fixed_number_and_has_count_select():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]

    assert "instanceNumberLabel" in render_instance_js
    assert "instance.display_index" not in instance_card
    assert "renderInstanceCountSelect" in render_instance_js
    assert 'name="instance_generation_count"' in render_instance_js
    assert "generation_params.n" in render_instance_js
    assert "copyAction" in render_instance_js


def test_v067_instance_provider_editor_uses_wider_select_space():
    css = read_frontend("styles.css")

    provider_row_css = css[
        css.find(".provider-source-row.is-editable {") :
        css.find(".provider-source-row > span:first-child")
    ]
    manual_provider_css = css[
        css.find(".manual-provider-input {") :
        css.find(".manual-provider-input select")
    ]
    provider_select_css = css[
        css.find(".manual-provider-input select") :
        css.find(".instance-count-input")
    ]

    assert "grid-template-columns: minmax(0, 1fr) auto;" in provider_row_css
    assert "grid-template-columns: auto minmax(0, 1fr);" in manual_provider_css
    assert "min-width: 0;" in provider_select_css
    assert "max-width: 100%;" in provider_select_css


def test_v067_single_save_input_clear_uses_operation_right_boundary():
    css = read_frontend("styles.css")
    input_column_css = css[
        css.find(".save-list.is-single .instance-card .record-input-images") :
        css.find(".save-list.is-single .instance-card .record-output-image")
    ]

    assert "grid-column: 3 / 5;" in input_column_css


def test_v067_instance_edit_save_is_undoable_and_provider_sync_not_source_blocked():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    lightbox_js = (ROOT / "frontend" / "js" / "lightbox.js").read_text(encoding="utf-8")
    save_fn = actions_js[
        actions_js.find("async function saveInstanceDraft") :
        actions_js.find("function fallbackCopyText")
    ]
    sync_fn = lightbox_js[
        lightbox_js.find("function syncInstanceDraftFromDom") :
        lightbox_js.find("function syncVisibleManagerState")
    ]

    assert "createSessionSnapshot()" in save_fn
    assert "hasInstanceDraftChanged" in save_fn
    assert "state.undoStack" in save_fn
    assert 'provider_key' in sync_fn
    assert '(draft.source || "manual") !== "generated"' not in sync_fn
    assert 'name="instance_provider"' in sync_fn
    assert 'name="instance_generation_count"' in sync_fn


def test_v067_history_record_prefers_instance_fixed_number_and_four_digit_labels():
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    record_fn = render_history_js[
        render_history_js.find("function renderHistoryRecord") :
        render_history_js.find("function renderHistoryPage")
    ]

    assert "record.instance_number" in record_fn
    assert 'padStart(4, "0")' in record_fn
    assert "save_display_index" not in record_fn
    assert "record.history_number_label" in record_fn
    assert "record.history_number || record.display_index || index + 1" in record_fn


def test_v027_pending_instances_use_frontend_timer_without_generation_label():
    app_js = read_frontend("app.js")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    pending_timer_fn = render_instance_js[
        render_instance_js.find("function formatPendingElapsed") :
        render_instance_js.find("function renderInstanceSelection")
    ]

    assert "pending_label: \"生成中\"" not in app_js
    assert "started_at_ms" in app_js
    assert "formatPendingElapsed" in app_js
    assert "startPendingTimer" in app_js
    assert "stopPendingTimerIfIdle" in app_js
    assert ".toFixed(1)" in pending_timer_fn
    assert " s" in pending_timer_fn


def test_v028_pending_instances_merge_with_running_database_instances():
    app_js = read_frontend("app.js")

    assert "function pendingMergeKey" in app_js
    assert "function mergePendingWithInstances" in app_js
    assert "generation_task_id" in app_js
    assert "generation_output_index" in app_js
    assert "generation_status === \"running\"" in app_js
    assert "renderPendingProcessInstances(pendingInstances)" in app_js
    assert "!Number.isFinite(Number(item?.id))" in app_js


def test_v028_copy_submit_and_failed_retry_are_distinct_actions():
    app_js = read_frontend("app.js")
    render_instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]

    assert "async function copySubmitInstance" in app_js
    assert "async function retryFailedInstance" in app_js
    assert 'data-action="copy-submit-instance"' in render_instance_card
    assert 'data-action="retry-failed-instance"' in render_instance_card
    assert "复制" in render_instance_card
    assert "重提" in render_instance_card
    assert '"retry_instance_id"' in app_js


def test_v047_copy_submit_and_failed_retry_use_original_instance_resolution():
    app_js = read_frontend("app.js")
    options_fn = app_js[
        app_js.find("function generationOptionsForInstance") : app_js.find("function pendingInstanceCountForPayload")
    ]
    copy_fn = app_js[
        app_js.find("async function copySubmitInstance") : app_js.find("async function retryFailedInstance")
    ]
    retry_fn = app_js[
        app_js.find("async function retryFailedInstance") : app_js.find("async function cancelGenerationTask")
    ]

    assert "params.resolved_size || params.size || item?.generation_size" in options_fn
    assert "params.resolution_level || params.resolution" in options_fn
    assert "params.ratio" in options_fn
    assert "aspectRatioForSize(resolvedSize" in options_fn
    assert "sizeForAspectRatio(ratio, resolutionLevel)" in options_fn
    assert "n: 1" in options_fn
    assert "const options = generationOptionsForInstance(item);" in copy_fn
    assert "const options = generationOptionsForInstance(instance);" in retry_fn
    assert "ratio: state.operation.aspect_ratio || defaultAspectRatio()" not in copy_fn
    assert "ratio: state.operation.aspect_ratio || defaultAspectRatio()" not in retry_fn


def test_v028_tags_are_immediate_outside_edit_mode():
    app_js = read_frontend("app.js")
    render_instance_card = app_js[
        app_js.find("function renderInstanceCard") : app_js.find("function renderInstanceTagEditor")
    ]

    assert "const tagEditable = !pending;" in render_instance_card
    assert "editable: tagEditable" in render_instance_card
    assert "/tags/add" in app_js
    assert "/tags/remove" in app_js
    assert "addInstanceTagImmediate" in app_js
    assert "removeInstanceTagImmediate" in app_js


def test_v028_document_level_batch_save_and_image_stabilizer_exist():
    app_js = read_frontend("app.js")

    assert "function handleDocumentBatchSaveBoundary" in app_js
    assert 'document.addEventListener("click", handleDocumentBatchSaveBoundary, true)' in app_js
    assert "function stabilizeSaveAreaImages" in app_js
    assert "function wakeVisibleSaveImages" in app_js
    assert "requestAnimationFrame" in app_js
    assert "data-lazy-image-path" in app_js


def test_v029_pending_timer_uses_stable_task_output_key():
    app_js = read_frontend("app.js")

    assert "function runningInstanceKey" in app_js
    assert "data-pending-elapsed-key" in app_js
    assert "pendingStartedAtByKey" in app_js
    assert "generation_task_id" in app_js
    assert "generation_output_index" in app_js
    timer_fn = app_js[
        app_js.find("function updatePendingTimerNodes") :
        app_js.find("function stopPendingTimerIfIdle")
    ]
    assert "[data-pending-elapsed-key]" in timer_fn
    assert "data-pending-elapsed\"" not in timer_fn


def test_v029_nodes_module_actions_and_persistence_exist():
    app_js = read_frontend("app.js")
    raw_app_js = read_frontend_raw("app.js")

    assert 'import "./js/nodes.js";' in raw_app_js
    assert "nodeFilter" in app_js
    assert "node_filter_path" in app_js
    assert "renderNodeControls" in app_js
    assert "loadNodes" in app_js
    assert "/api/nodes" in app_js
    assert 'params.set("node_filter_type"' in app_js
    assert 'params.set("node_id"' in app_js
    assert 'data-node-option-kind="new"' in app_js
    assert 'data-action="move-instance"' not in app_js
    assert 'data-action="batch-move-instances"' in app_js
    assert "/api/instances/batch/move" in app_js
    assert "window.prompt" not in (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    assert "data-node-level" in app_js
    assert "data-parent-id" in app_js


def test_v029_instance_tag_clear_and_outside_close_are_wired():
    app_js = read_frontend("app.js")

    assert "/tags/clear" in app_js
    assert "clearInstanceTagsImmediate" in app_js
    assert "closeTagSelectors" in app_js
    assert ".tag-selector" in app_js
    clear_handler = app_js[
        app_js.find('if (action === "clear-tag-selector")') :
        app_js.find('if (action === "toggle-tag-filter-dropdown")')
    ]
    assert "event.stopPropagation()" in clear_handler


def test_v029_image_loader_module_rebinds_lazy_images_after_paging():
    app_js = read_frontend("app.js")
    raw_app_js = read_frontend_raw("app.js")

    assert 'import "./js/image-loader.js";' in raw_app_js
    assert "IntersectionObserver" in app_js
    assert "forceVisible" in app_js
    assert "data-lazy-image-path" in app_js
    assert "wakeVisibleSaveImages" in app_js
    assert "visibilitychange" in app_js
    assert "naturalWidth === 0" in app_js


def test_v029_save_toolbar_contains_node_and_batch_move_controls():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    assert "节点" in app_js
    assert "批量移动" in app_js
    assert "总数" in app_js
    assert "save-toolbar-pagination" in app_js
    assert "batch-move-instances" in app_js
    assert "复制提交" not in app_js
    assert "重新提交" not in app_js
    assert "重提" in app_js
    assert ".node-controls" in css
    assert ".move-dialog" in css


def test_v029_move_dialog_uses_path_style_node_controls():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")

    assert "chooseMoveNode" in nodes_js
    assert "renderNodePathSelectors(" in nodes_js
    assert "flattenNodes" not in nodes_js[nodes_js.find("function chooseMoveNode"):nodes_js.find("Object.assign", nodes_js.find("function chooseMoveNode"))]
    assert "data-move-node-level" in nodes_js
    assert "data-move-parent-id" in nodes_js


def test_v030_save_area_has_pending_section_and_undo_redo_toolbar():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")

    save_area = app_js[
        app_js.find("function renderSaveArea") : app_js.find("Object.assign(globalThis", app_js.find("function renderSaveArea"))
    ]
    batch_toolbar = app_js[
        app_js.find("function renderBatchToolbar") : app_js.find("function renderSaveArea")
    ]
    assert "pending-section" in save_area
    assert "pending-list" in save_area
    assert "const runningInstances = realInstances.filter" not in save_area
    assert "const formalInstances = realInstances;" in save_area
    assert "renderPendingProcessInstances(pendingInstances)" in save_area
    assert "const cards = formalInstances.map" in save_area
    assert 'data-action="undo-last-action"' in batch_toolbar
    assert 'data-action="redo-last-action"' in batch_toolbar
    assert ".pending-section" in css


def test_v030_nodes_area_removes_standalone_create_button_and_uses_compact_path_ui():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    render_controls = nodes_js[nodes_js.find("function renderNodeControls"):nodes_js.find("function openNodeNameDialog")]
    assert 'data-node-option-kind="new"' in nodes_js
    assert "title=" in nodes_js
    assert "truncateNodeLabel" in nodes_js
    assert "data-node-display" in nodes_js
    assert "node-select-wrap" in nodes_js
    assert 'data-action="rename-current-node"' not in render_controls
    assert 'data-action="delete-current-node"' not in render_controls
    assert ".node-select" in css
    assert ".node-select-wrap" in css
    assert ".node-select-display" in css


def test_v030_node_name_dialog_validates_in_place_before_closing():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    dialog_fn = nodes_js[nodes_js.find("function openNodeNameDialog"):nodes_js.find("async function createNodeFromDialog")]
    create_fn = nodes_js[nodes_js.find("async function createNodeFromDialog"):nodes_js.find("async function renameCurrentNode")]
    rename_fn = nodes_js[nodes_js.find("async function renameNodeById"):nodes_js.find("async function renameCurrentNode")]

    assert "validateNodeNameLocally" in nodes_js
    assert 'data-node-name-error' in dialog_fn
    assert "setError" in dialog_fn
    assert "setPending" in dialog_fn
    assert 'if (event.key === "Enter")' in dialog_fn
    assert "validate: (name) => validateNodeNameLocally(name, parentId)" in create_fn
    assert "initialValue: currentNode?.name || \"\"" in rename_fn
    assert "validate: (name) => validateNodeNameLocally(name, parentId, nodeId)" in rename_fn
    assert ".field-error" in css


def test_v030_tag_selector_keeps_open_after_instance_selection():
    tags_js = (ROOT / "frontend" / "js" / "tags.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")

    select_fn = tags_js[tags_js.find("function selectTagChoice"):tags_js.find("function addTagFromDraft")]
    add_instance_fn = actions_js[actions_js.find("function addInstanceTag(instanceId)"):actions_js.find("function removeInstanceTag(instanceId, index)")]
    assert "target.tag_selector_open = true;" in select_fn
    assert "addInstanceTagImmediate(instanceId, nextTag, { keepOpen: true })" in select_fn
    assert "addInstanceTagImmediate(instanceId, exact || draft, { keepOpen: true })" in add_instance_fn


def test_v030_state_supports_undo_redo_history():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")

    assert "undoStack" in state_js
    assert "redoStack" in state_js


def test_v031_version_assets_and_launcher_are_updated():
    app_js = read_frontend("app.js")
    index_html = read_frontend("index.html")
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")

    assert 'const APP_VERSION = "V0.71";' in app_js
    assert "/static/styles.css?v=V0.71" in index_html
    assert "/static/app.js?v=V0.71" in index_html
    assert "Close the old service and restart V0.71 in this CMD" in launcher


def test_v031_image_stabilizer_verifies_current_page_images_after_render():
    app_js = read_frontend("app.js")
    image_loader_js = (ROOT / "frontend" / "js" / "image-loader.js").read_text(encoding="utf-8")
    actions_manager_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")

    assert "function verifySaveAreaImages" in image_loader_js
    assert "SAVE_IMAGE_VERIFY_DELAYS" in image_loader_js
    assert "isImageReady" in image_loader_js
    assert "dataset.lazyRetryCount" in image_loader_js
    assert 'img.loading = "eager"' in image_loader_js
    assert "finalPass" in image_loader_js
    assert "console.warn" in image_loader_js
    assert "unresolvedSaveAreaImages" in image_loader_js
    assert "saveAreaImageVerifyRunId" in image_loader_js
    assert "if (runId && runId !== saveAreaImageVerifyRunId)" in image_loader_js
    assert "img.complete && img.naturalWidth === 0" in image_loader_js
    assert "retry && img.getAttribute(\"src\") && !img.complete" in image_loader_js
    assert "img.naturalWidth === 0 || retry" not in image_loader_js
    assert "stabilizeSaveAreaImages?.({ forceVisible: true" in app_js
    assert "function stabilizeSaveAreaImages" not in actions_manager_js
    assert "  stabilizeSaveAreaImages," not in actions_manager_js
    assert "globalThis.stabilizeSaveAreaImages?.(" in actions_manager_js


def test_v031_node_dropdown_uses_custom_menu_with_create_first_and_context_menu():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "function nodeSelectionLabel" in nodes_js
    assert "function renderNodeMenuOptions" in nodes_js
    menu_fn = nodes_js[nodes_js.find("function renderNodeMenuOptions"):nodes_js.find("function renderNodePathSelectors")]
    assert menu_fn.find('data-node-option-kind="new"') < menu_fn.find('data-node-option-kind="all"')
    assert menu_fn.find('data-node-option-kind="all"') < menu_fn.find('data-node-option-kind="unassigned"')
    assert '"toggle-node-menu"' in nodes_js
    assert '"select-node-option"' in nodes_js
    assert 'data-node-context-id' in nodes_js
    assert 'data-action="rename-node-from-menu"' in nodes_js
    assert 'data-action="delete-node-from-menu"' in nodes_js
    assert ".node-menu" in css
    assert ".node-menu-option.is-create" in css
    assert ".node-context-menu" in css


def test_v031_undo_redo_labels_and_styles_are_distinct_from_pagination():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")
    batch_toolbar = app_js[
        app_js.find("function renderBatchToolbar") : app_js.find("function renderSaveArea")
    ]

    assert ">向后<" not in batch_toolbar
    assert ">向前<" not in batch_toolbar
    assert ">撤销<" in batch_toolbar
    assert ">重做<" in batch_toolbar
    assert 'class="undo-redo-button"' in batch_toolbar
    assert ".undo-redo-button" in css


def test_v032_version_assets_and_launcher_are_updated():
    app_js = read_frontend("app.js")
    index_html = read_frontend("index.html")
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert 'const APP_VERSION = "V0.71";' in app_js
    assert "/static/styles.css?v=V0.71" in index_html
    assert "/static/app.js?v=V0.71" in index_html
    assert "Close the old service and restart V0.71 in this CMD" in launcher


def test_v032_save_area_arrow_keyboard_paging_is_guarded_and_reuses_pagination():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")

    assert "saveAreaKeyboardFocus" in state_js
    assert "function isSaveAreaKeyboardTextTarget" in events_js
    assert "function hasBlockingSaveAreaKeyboardLayer" in events_js
    assert "function handleSaveAreaKeyboardPaging" in events_js
    assert "function handleSaveAreaKeyboardFocusPointerDown" in events_js
    assert "function handleSaveAreaKeyboardFocusIn" in events_js
    assert 'document.addEventListener("pointerdown", handleSaveAreaKeyboardFocusPointerDown, true)' in events_js
    assert 'document.addEventListener("focusin", handleSaveAreaKeyboardFocusIn, true)' in events_js
    assert "changeSavePage(-1)" in events_js
    assert "changeSavePage(1)" in events_js

    keydown_handler = events_js[events_js.find('document.addEventListener("keydown"'):]
    assert keydown_handler.find('event.key === "ArrowLeft" && state.lightbox.path') < keydown_handler.find("handleSaveAreaKeyboardPaging(event)")
    assert keydown_handler.find('event.key === "ArrowRight" && state.lightbox.path') < keydown_handler.find("handleSaveAreaKeyboardPaging(event)")

    paging_fn = events_js[
        events_js.find("function handleSaveAreaKeyboardPaging") :
        events_js.find('document.addEventListener("keydown"')
    ]
    assert "event.ctrlKey" in paging_fn
    assert "event.shiftKey" in paging_fn
    assert "event.altKey" in paging_fn
    assert "event.metaKey" in paging_fn
    assert "isSaveAreaKeyboardTextTarget(event.target)" in paging_fn
    assert "hasBlockingSaveAreaKeyboardLayer()" in paging_fn
    assert "state.page !== \"manager\"" in paging_fn
    assert "state.filters.page <= 1" in paging_fn
    assert "state.filters.page >= totalPages" in paging_fn


def test_v032_new_button_is_removed_from_save_toolbar_after_v062():
    app_js = read_frontend("app.js")
    css = read_frontend("styles.css")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    batch_toolbar = render_save_js[
        render_save_js.find("function renderBatchToolbar") : render_save_js.find("function renderSaveArea")
    ]
    save_toolbar = render_save_js[
        render_save_js.find("function renderSaveArea") : render_save_js.find("Object.assign(globalThis", render_save_js.find("function renderSaveArea"))
    ]
    toolbar_actions = save_toolbar[
        save_toolbar.find('class="toolbar-actions"') : save_toolbar.find("</form>")
    ]

    assert 'data-action="clear-selection"' in batch_toolbar
    assert 'class="new-instance-button" data-action="new-manual-instance"' not in batch_toolbar
    assert 'data-action="new-manual-instance"' not in toolbar_actions
    assert ".new-instance-button" in css
    assert ".new-instance-button:hover" in css
    assert app_js.count('data-action="new-manual-instance"') <= 1


def test_v033_version_assets_and_launcher_are_updated():
    app_js = read_frontend("app.js")
    index_html = read_frontend("index.html")
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert 'const APP_VERSION = "V0.71";' in app_js
    assert "/static/styles.css?v=V0.71" in index_html
    assert "/static/app.js?v=V0.71" in index_html
    assert "Close the old service and restart V0.71 in this CMD" in launcher


def test_v033_prompt_search_clear_button_is_inside_search_input_and_refreshes():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis", render_save_js.find("function renderSaveArea"))
    ]
    search_wrap = save_area[
        save_area.find('class="toolbar-search-wrap"') :
        save_area.find('data-action="apply-prompt-search"')
    ]

    assert 'class="toolbar-search-wrap"' in save_area
    assert 'name="q"' in search_wrap
    assert 'class="prompt-clear search-prompt-clear"' in search_wrap
    assert 'data-action="clear-prompt-search"' in search_wrap
    assert 'data-skip-batch-save="true"' in search_wrap
    assert "function clearPromptSearch" in actions_js
    clear_fn = actions_js[
        actions_js.find("function clearPromptSearch") :
        actions_js.find("function operationPayload")
    ]
    assert 'state.filters.q = "";' in clear_fn
    assert "state.filters.page = 1;" in clear_fn
    assert "clearCurrentPageSelection();" in clear_fn
    assert "persistUiState();" in clear_fn
    assert "refreshInstances()" in clear_fn
    assert 'action === "clear-prompt-search"' in events_js
    assert "clearPromptSearch();" in events_js
    assert ".toolbar-search-wrap" in css
    assert ".search-prompt-clear" in css
    assert "padding-right:" in css[css.find(".toolbar-search-wrap input") : css.find(".toolbar-search-wrap input") + 160]


def test_v035_prompt_search_clear_button_has_own_absolute_layout():
    css = read_frontend("styles.css")

    search_clear_css = css[
        css.find(".toolbar-search-wrap .search-prompt-clear") :
        css.find("}", css.find(".toolbar-search-wrap .search-prompt-clear"))
    ]
    prompt_shell_css = css[
        css.find(".prompt-shell textarea") :
        css.find("}", css.find(".prompt-shell textarea"))
    ]

    assert "position: absolute;" in search_clear_css
    assert "width: 22px;" in search_clear_css
    assert "height: 22px;" in search_clear_css
    assert "min-height: 22px;" in search_clear_css
    assert "opacity: 0;" in search_clear_css
    assert "pointer-events: none;" in search_clear_css
    assert "position: absolute;" not in prompt_shell_css


def test_v033_instance_prompt_clear_button_only_appears_while_editing_and_updates_draft():
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    editable_prompt_fn = render_operation_js[
        render_operation_js.find("function renderEditablePromptField") :
        render_operation_js.find("function renderReadonlyPromptField")
    ]
    instance_card_fn = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]
    prompt_call = instance_card_fn[
        instance_card_fn.find("renderPromptField({") :
        instance_card_fn.find("})}", instance_card_fn.find("renderPromptField({"))
    ]
    clear_fn = actions_js[
        actions_js.find("function clearInstancePrompt") :
        actions_js.find("function operationPayload")
    ]

    assert 'data-id="${escapeHtml(instanceId)}"' in editable_prompt_fn
    assert 'data-skip-batch-save="true"' in editable_prompt_fn
    assert 'clearAction: editable ? "clear-instance-prompt" : ""' in prompt_call
    assert "copyAction: \"copy-instance-prompt\"" in prompt_call
    assert "function clearInstancePrompt(instanceId)" in actions_js
    assert 'draft.prompt = "";' in clear_fn
    assert "state.editing.get" in clear_fn
    assert "autoGrowPromptTextarea(input)" in clear_fn
    assert "api(" not in clear_fn
    assert "saveInstanceDraft" not in clear_fn
    assert 'action === "clear-instance-prompt"' in events_js
    assert "clearInstancePrompt(actionNode.dataset.id);" in events_js


def test_v034_small_images_use_thumbnail_but_lightbox_uses_original():
    lightbox_js = (ROOT / "frontend" / "js" / "lightbox.js").read_text(encoding="utf-8")
    image_loader_js = (ROOT / "frontend" / "js" / "image-loader.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")

    assert "function thumbnailUrl(path)" in lightbox_js
    assert "`/api/thumbnail?path=${encodeURIComponent(path)}`" in lightbox_js
    assert "`/api/image?path=${encodeURIComponent(path)}`" in lightbox_js
    assert "thumbnailUrl(path)" in image_loader_js
    assert "function lazyImageDisplayUrl" in image_loader_js
    assert "src.startsWith(expectedThumbnail)" in image_loader_js
    assert '<img src="${escapeHtml(thumbnailUrl(path))}"' in render_operation_js
    assert 'src="${escapeHtml(imageUrl(state.lightbox.path))}"' in render_instance_js


def test_v034_data_safety_exposes_thumbnail_cache_controls():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_data_safety_js = (ROOT / "frontend" / "js" / "render-data-safety.js").read_text(encoding="utf-8")
    actions_data_safety_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "thumbnailCache" in state_js
    assert "clearingThumbnails" in state_js
    assert "缩略图缓存" in render_data_safety_js
    assert "清理缩略图缓存" in render_data_safety_js
    assert "data-action=\"clear-thumbnail-cache\"" in render_data_safety_js
    assert "/api/thumbnails/stats" in actions_data_safety_js
    assert "/api/thumbnails/clear" in actions_data_safety_js
    assert "function loadThumbnailCacheStats" in actions_data_safety_js
    assert "function clearThumbnailCache" in actions_data_safety_js
    assert 'action === "clear-thumbnail-cache"' in events_js
    assert "loadThumbnailCacheStats().catch" in events_js
    assert ".thumbnail-cache-meta" in css


def test_v035_prompt_clear_moves_to_title_row_before_copy():
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    editable_prompt_fn = render_operation_js[
        render_operation_js.find("function renderEditablePromptField") :
        render_operation_js.find("function renderReadonlyPromptField")
    ]
    title_row = editable_prompt_fn[
        editable_prompt_fn.find('class="field-title-row"') :
        editable_prompt_fn.find("</div>", editable_prompt_fn.find('class="field-title-row"'))
    ]
    prompt_shell = editable_prompt_fn[
        editable_prompt_fn.find('class="prompt-shell"') :
        editable_prompt_fn.find("</div>", editable_prompt_fn.find('class="prompt-shell"'))
    ]

    assert 'class="field-title-actions"' in editable_prompt_fn
    assert 'class="field-title-action prompt-title-clear"' in editable_prompt_fn
    assert ">清除</button>" in editable_prompt_fn
    assert "clearTitleButton" in editable_prompt_fn
    assert 'field-title-action-slot field-title-clear-slot' in editable_prompt_fn
    assert 'field-title-action-slot field-title-copy-slot' in editable_prompt_fn
    assert 'field-title-action-slot field-title-count-slot' in editable_prompt_fn
    assert editable_prompt_fn.find("const clearTitleButton") < editable_prompt_fn.find("const copyButton")
    assert "clearButton" not in editable_prompt_fn
    assert "prompt-clear" not in prompt_shell
    textarea_css = css[
        css.find(".prompt-shell textarea") :
        css.find("}", css.find(".prompt-shell textarea"))
    ]
    assert "padding-right: 32px;" not in textarea_css
    assert ".prompt-title-clear" in css
    assert ".search-prompt-clear" in css


def test_v035_node_name_dialog_enter_confirms_escape_cancels():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    dialog_fn = nodes_js[
        nodes_js.find("function openNodeNameDialog") :
        nodes_js.find("async function createNodeFromDialog")
    ]

    assert 'event.key === "Enter"' in dialog_fn
    assert 'event.key === "Escape"' in dialog_fn
    assert "event.preventDefault();" in dialog_fn
    assert "close(undefined);" in dialog_fn
    assert "createNodeFromDialog" in nodes_js
    assert "renameNodeById" in nodes_js


def test_v035_batch_toolbar_labels_are_shorter_and_ordered():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    batch_toolbar = render_save_js[
        render_save_js.find("function renderBatchToolbar") :
        render_save_js.find("function renderSaveArea")
    ]

    assert ">全选</button>" in batch_toolbar
    assert ">取消</button>" in batch_toolbar
    assert "已选 ${escapeHtml(selectedCount)}" in batch_toolbar
    assert ">添加标签</button>" in batch_toolbar
    assert ">删除标签</button>" not in batch_toolbar
    assert ">移动</button>" in batch_toolbar
    assert ">删除</button>" in batch_toolbar
    assert ">提交</button>" in batch_toolbar
    assert ">复制</button>" in batch_toolbar
    assert "全选当前页" not in batch_toolbar
    assert "批量添加标签" not in batch_toolbar
    assert "批量删除标签" not in batch_toolbar
    assert "批量移动</button>" not in batch_toolbar
    assert "批量删除</button>" not in batch_toolbar
    assert "清空选择" not in batch_toolbar
    assert batch_toolbar.find('data-action="select-current-page"') < batch_toolbar.find('data-action="clear-selection"')
    assert batch_toolbar.find('data-action="clear-selection"') < batch_toolbar.find('class="batch-count"')
    assert 'data-action="batch-add-tags"' in batch_toolbar
    assert 'data-action="batch-remove-tags"' not in batch_toolbar
    assert 'data-action="batch-move-instances"' in batch_toolbar
    assert 'data-action="batch-delete-instances"' in batch_toolbar
    assert 'data-action="batch-submit-instances"' in batch_toolbar
    assert 'data-action="batch-copy-instances"' in batch_toolbar


def test_v036_thumbnail_view_state_toolbar_and_persistence_exist():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")

    batch_toolbar = render_save_js[
        render_save_js.find("function renderBatchToolbar") :
        render_save_js.find("function renderSaveArea")
    ]
    save_area_fn = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis")
    ]

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert 'const APP_VERSION = "V0.71";' in read_frontend("app.js")
    assert "title AI Image Manager V0.71" in launcher
    assert 'saveViewMode: "list"' in state_js
    assert 'save_view_mode: "list"' in persistence_js
    assert "persistedSaveViewMode" in persistence_js
    assert 'state.saveViewMode = normalizeOption(saved.save_view_mode' in persistence_js
    assert 'data-action="toggle-thumbnail-view"' in batch_toolbar
    assert "缩略图" in batch_toolbar
    assert "列表" in batch_toolbar
    assert 'data-action="new-manual-instance"' not in batch_toolbar
    assert 'data-action="toggle-thumbnail-view"' in batch_toolbar
    assert "isThumbnailView" in batch_toolbar
    assert "thumbnailActionDisabled" not in batch_toolbar
    assert 'name="save_layout" ${isThumbnailView ? "disabled" : ""}' in save_area_fn
    assert "toggleSaveThumbnailView" in actions_js
    toggle_fn = actions_js[
        actions_js.find("function toggleSaveThumbnailView") :
        actions_js.find("function renderPathPreview")
    ]
    assert "pruneSelectionToCurrentPage();" in toggle_fn
    assert "persistUiState();" in toggle_fn
    assert "stabilizeSaveAreaImages" in toggle_fn
    assert 'action === "toggle-thumbnail-view"' in events_js


def test_v036_thumbnail_grid_renders_output_only_with_lazy_hover_and_pending_timer():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    lightbox_js = (ROOT / "frontend" / "js" / "lightbox.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    thumbnail_fn = render_save_js[
        render_save_js.find("function renderInstanceThumbnailTile") :
        render_save_js.find("function renderThumbnailSaveGrid")
    ]
    grid_fn = render_save_js[
        render_save_js.find("function renderThumbnailSaveGrid") :
        render_save_js.find("function renderSaveArea")
    ]

    assert "function renderInstanceThumbnailTile" in render_save_js
    assert "function renderThumbnailSaveGrid" in render_save_js
    assert "save-thumbnail-grid" in render_save_js
    assert "save-thumbnail-tile" in render_save_js
    assert "data-image-path" in thumbnail_fn
    assert "data-lazy-image-path" in thumbnail_fn
    assert "thumbnailUrl(path)" in thumbnail_fn
    assert "output_image_path" in thumbnail_fn
    assert "input_image_paths" not in thumbnail_fn
    assert "instance_prompt" not in thumbnail_fn
    assert "copy-submit-instance" not in thumbnail_fn
    assert "pendingStatusText(instance, pendingStartMs)" in thumbnail_fn
    assert "data-pending-elapsed-key" in thumbnail_fn
    assert "无输出" in thumbnail_fn
    assert "失败" in thumbnail_fn
    assert "processInstances" in grid_fn
    assert "formalInstances" in grid_fn
    assert "save-thumbnail-grid" in css
    assert "save-thumbnail-tile" in css
    assert "aspect-ratio: 1 / 1;" in css
    assert "galleryForThumbnailGrid" in lightbox_js
    assert 'closest?.(".save-thumbnail-grid")' in lightbox_js


def test_v040_instance_bring_in_button_order_and_thumbnail_view_excludes_it():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")

    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]
    manual_action = instance_card[
        instance_card.find("const copyAction") :
        instance_card.find("const inlineActions")
    ]
    normal_actions = instance_card[
        instance_card.find('data-action="bring-instance-to-operation"') :
        instance_card.find("${submitAction}") + 80
    ]
    failed_actions = instance_card[
        instance_card.find('data-action="bring-instance-to-operation"') :
        instance_card.find('data-action="retry-failed-instance"') + 80
    ]
    thumbnail_fn = render_save_js[
        render_save_js.find("function renderInstanceThumbnailTile") :
        render_save_js.find("function renderThumbnailSaveGrid")
    ]

    assert 'data-action="bring-instance-to-operation"' in instance_card
    assert ">带入<" in instance_card
    assert 'data-action="copy-submit-instance"' in manual_action
    assert 'data-action="submit-manual-instance"' in manual_action
    assert normal_actions.find('bring-instance-to-operation') < normal_actions.find('copyAction')
    assert failed_actions.find('bring-instance-to-operation') < failed_actions.find('retry-failed-instance')
    assert 'data-action="move-instance"' not in instance_card
    assert "bring-instance-to-operation" not in thumbnail_fn


def test_v040_history_records_have_bring_in_action_and_events():
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    history_record = render_history_js[
        render_history_js.find("function renderHistoryRecord") :
        render_history_js.find("function renderHistoryPage")
    ]

    assert 'data-action="bring-history-to-operation"' in history_record
    assert 'data-history-id="${escapeHtml(record.id || "")}"' in history_record
    assert ">带入<" in history_record
    assert "async function bringHistoryToOperation" in actions_js
    assert "async function bringInstanceToOperation" in actions_js
    assert "function applyBringInToOperation" in actions_js
    assert 'action === "bring-history-to-operation"' in events_js
    assert 'action === "bring-instance-to-operation"' in events_js


def test_v040_bring_in_preserves_history_snapshot_without_output_image():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")

    apply_fn = actions_js[
        actions_js.find("function applyBringInToOperation") :
        actions_js.find("async function bringInstanceToOperation")
    ]
    history_fn = actions_js[
        actions_js.find("async function bringHistoryToOperation") :
        actions_js.find("function operationPayload")
    ]

    assert "state.operation.prompt" in apply_fn
    assert "state.operation.input_image_paths" in apply_fn
    assert "state.operation.tags" in apply_fn
    assert "state.operation.output_image_path" not in apply_fn
    assert "const targetProvider = activeProvider();" in apply_fn
    assert "providerCallMethodCapability(targetProvider)" in apply_fn
    assert "supportsImageToImage === false" in apply_fn
    assert "supportsTextToImage === false" in apply_fn
    assert "supportsCount === false" in apply_fn
    assert "persistUiState();" in apply_fn
    assert "record.params" in history_fn
    assert "bringInRecordTags(record)" in history_fn
    assert "api(" not in history_fn


def test_v042_provider_key_is_auto_generated_and_readonly_from_creation():
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")

    assert "function nextProviderKey" in actions_settings_js
    assert 'const prefix = "provider_";' in actions_settings_js
    assert "padStart(4, \"0\")" in actions_settings_js
    assert "const key = nextProviderKey(nextSettings.providers);" in actions_settings_js
    assert "new_provider" not in actions_settings_js
    assert 'input name="provider_key"' in render_settings_js
    assert 'readonly aria-readonly="true"' in render_settings_js
    assert 'state.settingsProviderDraftIsNew ? "" : "readonly"' not in render_settings_js
    assert "document.querySelector('[name=\"display_name\"]')?.focus();" in actions_settings_js


def test_v042_title_shows_local_logo_author_and_version():
    utils_js = (ROOT / "frontend" / "js" / "utils.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")
    logo_path = ROOT / "frontend" / "assets" / "logo.png"

    assert logo_path.is_file()
    assert "renderAppBrandMeta" in utils_js
    assert "/static/assets/logo.png" in utils_js
    assert "雾岛凛" in utils_js
    assert "app-logo" in utils_js
    assert "app-author" in utils_js
    assert "renderAppBrandMeta()" in utils_js
    brand_meta_fn = utils_js[
        utils_js.find("function renderAppBrandMeta") : utils_js.find("function mountAppVersionBadge")
    ]
    assert brand_meta_fn.find("renderAppVersionBadge()") < brand_meta_fn.find("app-logo")
    assert brand_meta_fn.find("app-logo") < brand_meta_fn.find("app-author")
    assert 'brand.insertAdjacentHTML("beforeend", renderAppVersionBadge())' not in utils_js
    assert ".app-logo" in css
    assert ".app-author" in css


def test_v042_settings_examples_are_loaded_from_shared_openai_scripts():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "openaiScriptExamples" in state_js
    assert 'api("/api/openai-script-examples")' in actions_settings_js
    assert "loadOpenAIScriptExamples" in actions_settings_js
    assert "state.openaiScriptExamples.text_to_image" in render_settings_js
    assert "state.openaiScriptExamples.image_to_image" in render_settings_js
    assert "from urllib.request import urlretrieve" not in render_settings_js
    assert "base_url=\"https://img.aiapis.help/v1\"" not in render_settings_js
    assert "await loadOpenAIScriptExamples().catch" in events_js
    assert "loadOpenAIScriptExamples().catch" in events_js


def test_v059_fixed_examples_ignore_legacy_saved_provider_code_examples():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")

    fixed_fn = render_settings_js[
        render_settings_js.find("function fixedCodeExample") :
        render_settings_js.find("function customScriptCode")
    ]
    assert "providerCodeValue" not in fixed_fn
    assert "code_examples" not in fixed_fn
    assert "return defaultCodeExample(callMethod, exampleMode);" in render_settings_js


def test_v059_switching_openai_example_mode_only_preserves_custom_script():
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "function syncSettingsProviderDraftFromForm(form, options = {})" in actions_settings_js
    assert "fixed_code_example" not in actions_settings_js
    assert 'code_examples: JSON.parse(JSON.stringify(existingProvider.code_examples || {}))' in actions_settings_js
    assert "const switchedOpenAIExampleMode = event.target.name === \"openai_example_mode\";" in events_js
    assert "const switchedAdapter = event.target.name === \"adapter\";" in events_js
    assert "syncSettingsProviderDraftFromForm(form);" in events_js
    assert "state.settingsCodeExample.editDraft = \"\";" in events_js


def test_v041_save_area_image_verification_polls_until_ready_before_warning():
    image_loader_js = (ROOT / "frontend" / "js" / "image-loader.js").read_text(encoding="utf-8")

    assert "SAVE_IMAGE_VERIFY_TIMEOUT_MS" in image_loader_js
    assert "SAVE_IMAGE_VERIFY_INTERVAL_MS" in image_loader_js
    assert "function collectUnresolvedSaveAreaImages" in image_loader_js
    assert "function scheduleNextSaveAreaImageVerification" in image_loader_js
    assert "if (!unresolvedSaveAreaImages.length) {" in image_loader_js
    assert "elapsedMs >= SAVE_IMAGE_VERIFY_TIMEOUT_MS" in image_loader_js
    assert "console.warn(\"Save-area images still not ready after verification\"" in image_loader_js


def test_v037_data_safety_uses_task_export_restore_preview_and_summary_ui():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_data_safety_js = (ROOT / "frontend" / "js" / "render-data-safety.js").read_text(encoding="utf-8")
    actions_data_safety_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert 'const APP_VERSION = "V0.71";' in read_frontend("app.js")
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert "/static/styles.css?v=V0.71" in read_frontend("index.html")
    assert "/static/app.js?v=V0.71" in read_frontend("index.html")
    assert "title AI Image Manager V0.71" in (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")
    assert "exportTaskId" in state_js
    assert "exportTask" in state_js
    assert "restorePreview" in state_js
    assert "function exportDataPackage" in actions_data_safety_js
    assert 'api("/api/exports", { method: "POST" })' in actions_data_safety_js
    assert 'api(`/api/exports/tasks/${state.dataSafety.exportTaskId}`)' in actions_data_safety_js
    assert 'api("/api/restore/preview"' in actions_data_safety_js
    assert "previewRestoreFile" in actions_data_safety_js
    assert "导出数据" in render_data_safety_js
    assert "导出 JSON" not in render_data_safety_js
    assert "renderDataSummary" in render_data_safety_js
    assert "restorePreview" in render_data_safety_js
    assert "缩略图缓存不是核心数据" in render_data_safety_js
    assert "正在创建恢复前备份" in actions_data_safety_js
    assert 'data-action="export-data"' in render_data_safety_js
    assert 'action === "export-data"' in events_js
    assert "exportDataPackage();" in events_js
    assert "previewRestoreFile" in events_js


def test_v038_tag_management_page_manages_only_used_tags():
    index_html = read_frontend("index.html")
    app_js = read_frontend("app.js")
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_tag_js = (ROOT / "frontend" / "js" / "render-tag-management.js").read_text(encoding="utf-8")
    actions_tag_js = (ROOT / "frontend" / "js" / "actions-tag-management.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert 'const APP_VERSION = "V0.71";' in app_js
    assert "/static/styles.css?v=V0.71" in index_html
    assert "/static/app.js?v=V0.71" in index_html
    assert 'data-page="tag-management"' in index_html
    assert "标签管理" in index_html
    assert "tagManagement" in state_js
    assert "renderTagManagementPage" in render_tag_js
    assert "loadTagManagementTags" in actions_tag_js
    assert 'api(`/api/tag-management?${params.toString()}`)' in actions_tag_js
    assert 'api(`/api/tag-management/${tagId}/rename`' in actions_tag_js
    assert 'api("/api/tag-management/merge"' in actions_tag_js
    assert 'data-action="rename-tag-management"' in render_tag_js
    assert 'data-action="open-merge-tag-management"' in render_tag_js
    assert 'data-action="create-tag-management"' not in render_tag_js
    assert "删除未使用" not in render_tag_js
    assert "__untagged__" in render_tag_js
    assert "无" in render_tag_js
    assert ".tag-management-panel" in css
    assert ".tag-management-card" in css


def test_v039_history_query_controls_and_cleanup_api_exist():
    app_js = read_frontend("app.js")
    index_html = read_frontend("index.html")
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert 'const APP_VERSION = "V0.71";' in app_js
    assert "/static/styles.css?v=V0.71" in index_html
    assert "/static/app.js?v=V0.71" in index_html
    assert "title AI Image Manager V0.71" in launcher
    assert 'data-page="tag-management"' in index_html
    assert 'q: ""' in state_js
    assert 'provider: "all"' in state_js
    assert 'call_method: "all"' in state_js
    assert 'start_date: ""' in state_js
    assert 'end_date: ""' in state_js
    assert "filterOptions" in state_js
    assert "history.q" in persistence_js
    assert "history.provider" in persistence_js
    assert "history.call_method" in persistence_js
    assert 'name="history_q"' in render_history_js
    assert 'name="history_provider"' in render_history_js
    assert 'name="history_call_method"' in render_history_js
    assert 'name="history_start_date"' in render_history_js
    assert 'name="history_end_date"' in render_history_js
    assert 'data-action="cleanup-failed-history"' not in render_history_js
    assert 'data-action="cleanup-history-before-date"' not in render_history_js
    assert "/api/generation-history/filter-options" in actions_js
    assert 'params.set("q", state.history.q || "")' in actions_js
    assert 'params.set("provider", state.history.provider || "all")' in actions_js
    assert 'params.set("call_method", state.history.call_method || "all")' in actions_js
    assert 'params.set("start_date", state.history.start_date || "")' in actions_js
    assert 'params.set("end_date", state.history.end_date || "")' in actions_js
    assert "/api/generation-history/cleanup/preview" in actions_js
    assert "/api/generation-history/cleanup/failed" in actions_js
    assert "/api/generation-history/cleanup/before-date" in actions_js
    assert "不会删除保存区实例" in actions_js
    assert "不会删除电脑上的图片文件" in actions_js
    assert 'action === "cleanup-failed-history"' not in events_js
    assert 'action === "cleanup-history-before-date"' not in events_js


def test_v043_thumbnail_and_list_selection_support_shift_batch_actions():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.71"
    assert 'const APP_VERSION = "V0.71";' in read_frontend("app.js")
    assert 'lastSelectedInstanceId: ""' in state_js
    assert 'if (state.saveViewMode === "thumbnail")' not in render_save_js[
        render_save_js.find("function currentPageSelectableIds") : render_save_js.find("function runningInstanceKey")
    ]
    assert "thumbnailActionDisabled" not in render_save_js
    assert 'selectedCount <= 0 ? "disabled" : ""' in render_save_js
    assert 'data-action="toggle-select-instance"' in render_save_js
    assert "thumbnail-select" in render_save_js
    assert "is-selected" in render_save_js
    assert 'event.shiftKey' in events_js
    assert "toggleSelectInstance(actionNode.dataset.id, { shiftKey: event.shiftKey });" in events_js
    assert "selectRangeToInstance" in actions_js
    assert "state.lastSelectedInstanceId" in actions_js
    assert "resetSelectionAnchor" in actions_js
    assert "选择</span>" not in render_instance_js
    assert 'aria-label="选择实例"' in render_instance_js
    assert ".thumbnail-select" in css
    assert ".save-thumbnail-tile.is-selected" in css
    assert ".save-thumbnail-tile:hover .thumbnail-select" in css


def test_v044_generation_retry_ui_and_script_hooks_exist():
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")
    runner_py = (ROOT / "backend" / "custom_script_runner.py").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    text_script = (ROOT.parent / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    image_script = (ROOT.parent / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")

    assert "RETRYABLE_STATUS_CODES = {429, 502, 503, 504}" in api_py
    assert "create_retry_history_record" in api_py
    assert "create_script_retry_history_records" in api_py
    assert '@api.post("/generate/cancel")' in api_py
    assert "retry_events" in runner_py
    assert "pendingStatusText" in render_instance_js
    assert 'data-action="cancel-generation-task"' in render_instance_js
    assert "pendingStatusText(instance, pendingStartMs)" in render_save_js
    assert "async function cancelGenerationTask" in actions_js
    assert 'action === "cancel-generation-task"' in events_js
    assert "retry_events" in text_script
    assert "is_retryable_error" in text_script
    assert "MAX_RETRY_ATTEMPTS" in text_script
    assert "download_image_once" in text_script
    assert "time.sleep(delay)" in text_script
    assert "retry_events" in image_script
    assert "is_retryable_error" in image_script
    assert "MAX_RETRY_ATTEMPTS" in image_script
    assert "download_image_once" in image_script
    assert "time.sleep(delay)" in image_script


def test_v045_pending_history_copy_and_no_operation_result_backfill():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    actions_data_safety_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "sortPendingInstancesForDisplay" in render_save_js
    assert "generation_started_at" in render_save_js
    assert "created_at" in render_save_js
    assert "pendingDisplayTime" in render_save_js
    assert "processInstances.sort(comparePendingInstancesForDisplay);" in render_save_js
    assert "historyVisibleErrorText" in render_history_js
    assert ".split(/\\r?\\n/)" in render_history_js
    assert ".slice(-3)" in render_history_js
    assert 'data-action="copy-history-field"' in render_history_js
    assert 'renderHistoryCopyButton(record, "prompt", "指令")' in render_history_js
    assert 'renderHistoryCopyButton(record, "params", "参数")' in render_history_js
    assert "function renderHistoryErrorButtons" in render_history_js
    assert 'renderHistoryCopyButton(record, "error", "错误", false)' in render_history_js
    assert "`错误${index + 1}`" in render_history_js
    assert 'disabled aria-disabled="true"' in render_history_js
    assert "copyHistoryField" in actions_js
    assert "historyFieldCopyText" in actions_js
    assert "closeHistoryTextPopover();" in actions_js[
        actions_js.find("function applyHistoryFilters") : actions_js.find("function clearTagFilter")
    ]
    assert "closeHistoryTextPopover();" in actions_js[
        actions_js.find("function setHistoryPage") : actions_js.find("function clearTagFilter")
    ]
    assert "closeHistoryTextPopover();" in actions_data_safety_js[
        actions_data_safety_js.find("async function loadGenerationHistory") : actions_data_safety_js.find("async function loadGenerationHistoryFilterOptions")
    ]
    assert "state.operation.output_image_path = outputPaths.at(-1)" not in actions_js
    assert 'action === "copy-history-field"' in events_js
    assert "copyHistoryField(actionNode.dataset.historyId, actionNode.dataset.historyField)" in events_js
    assert "closeHistoryTextPopover();" in events_js[
        events_js.find("tabs.forEach") : events_js.find("app.addEventListener(\"click\"")
    ]


def test_v0451_running_database_instances_render_cancelable_after_reload():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    assert "isRunningInstance" in render_instance_js
    assert "const pending = isRunningInstance(instance);" in render_instance_js
    assert 'data-action="cancel-generation-task"' in render_instance_js
    assert 'data-task-id="${escapeHtml(item.generation_task_id || item.task_id || "")}"' in render_instance_js
    assert "instance.generation_status === \"running\"" in render_save_js
    assert api_py.count("is_generation_task_cancelled(generation_task_id)") >= 3
    assert "GENERATION_PROVIDER_LOCKS" in api_py
    assert "provider_generation_lock" in api_py
    assert "with provider_generation_lock(provider_key):" in api_py
    assert "mark_precreated_failed(\"生成已取消\")" in api_py
    assert 'item.generation_status = "failed";' not in actions_js
    assert 'item.generation_error = "生成已取消";' not in actions_js
    assert "state.cancellingGenerationTaskIds.add(cleanId);" in actions_js


def test_v0451_provider_lock_covers_retry_loop_and_retry_limit_is_finite():
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")
    assert "GENERATION_RETRY_MAX_ATTEMPTS = 4" in api_py
    assert "with provider_generation_lock(provider_key):\n            while True:" in api_py


def test_v047_pending_retry_badge_and_running_refresh_exist():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "runningRefreshTimerId: 0" in state_js
    assert "runningRefreshInFlight: false" in state_js
    assert "function pendingRetryLabel" in render_instance_js
    assert "第${match[1]}次重试" in render_instance_js
    assert "retryLabel: pending ? pendingRetryLabel(item) : \"\"" in render_instance_js
    assert "field-title-retry" in render_operation_js
    assert ".field-title-retry" in css
    assert "function startRunningRefresh" in actions_js
    assert "window.setInterval(async () =>" in actions_js
    assert "await loadInstances();" in actions_js
    assert "syncRunningRefresh();" in render_operation_js


def test_v048_pending_retry_timer_only_shows_elapsed_seconds():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    start = render_instance_js.find("function pendingStatusText")
    end = render_instance_js.find("function pendingRetryLabel")
    assert start != -1 and end != -1
    pending_status_fn = render_instance_js[start:end]

    assert "generation_error" not in pending_status_fn
    assert "firstLine" not in pending_status_fn
    assert "重试中" not in pending_status_fn
    assert " · " not in pending_status_fn
    assert "return formatPendingElapsed(startedAtMs || item?.started_at_ms);" in pending_status_fn
    assert "node.textContent = item ? pendingStatusText(item, startedAtMs) : formatPendingElapsed(startedAtMs);" in actions_js

    retry_style = css[css.find(".field-title-retry") : css.find(".prompt-title-clear")]
    assert "color: #dc2626;" in retry_style
    assert ".field-title-row > .field-title-retry" in retry_style


def test_v048_settings_model_field_and_fixed_four_column_grids_exist():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert 'span>model</span>' in render_settings_js
    assert 'renderSettingHistoryInput("model"' in render_settings_js
    assert 'provider.model || ""' in render_settings_js
    assert 'formData.has("model") ? formData.get("model") : existingProvider.model || ""' in actions_settings_js
    assert 'model: "gpt-image-2"' not in actions_settings_js

    provider_grid = css[css.find(".provider-settings-grid") : css.find(".provider-identity-grid")]
    connection_grid = css[css.find(".connection-settings-grid") : css.find(".param-field")]
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in provider_grid
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in connection_grid
    assert "connection-model-field" in render_settings_js
    assert ".connection-model-field" in css


def test_v048_tag_management_uses_fixed_card_grid():
    render_tag_js = (ROOT / "frontend" / "js" / "render-tag-management.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "tag-management-card-grid" in render_tag_js
    assert "tag-management-card" in render_tag_js
    assert "tag-management-row tag-management-head" not in render_tag_js
    assert ".tag-management-card-grid" in css
    tag_grid_css = css[css.find(".tag-management-card-grid") : css.find(".tag-management-card {")]
    assert "grid-template-columns: repeat(8, minmax(0, 1fr));" in tag_grid_css


def test_v048_settings_help_and_connection_widths_are_aligned():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")
    connection_html = render_settings_js[
        render_settings_js.find('<div class="connection-settings-grid">') :
        render_settings_js.find('${renderAdapterSpecificSettings(provider)}')
    ]

    assert connection_html.find("<span>api_key</span>") < connection_html.find("填写 api_key 时优先使用 api_key")
    assert connection_html.find("填写 api_key 时优先使用 api_key") < connection_html.find('name="api_key"')
    assert connection_html.find('renderSettingHistoryInput("api_key_env"') > connection_html.find('name="api_key"')
    api_env_block = connection_html[
        connection_html.find("<span>api_key_env</span>") :
        connection_html.find('renderSettingHistoryInput("api_key_env"')
    ]
    assert "填写 api_key 时优先使用 api_key" not in api_env_block

    assert ".connection-api-key-field" in css
    assert ".connection-user-agent-field" in css
    assert ".connection-settings-grid .connection-api-key-field" in css
    assert ".connection-settings-grid .connection-user-agent-field" in css
    aligned_widths = css[
        css.find(".connection-settings-grid .connection-api-key-field") :
        css.find(".connection-settings-grid .connection-api-key-env-field")
    ]
    assert "grid-column: span 2;" in aligned_widths


def test_v048_path_replace_dialog_is_draggable_and_preview_expands():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "function makeDialogDraggable" in actions_js
    assert 'data-dialog-drag-handle' in actions_js
    assert "makeDialogDraggable(dialog, modal)" in actions_js
    assert 'data-action="path-replace"' in render_save_js
    assert "path-replace-modal" in actions_js
    assert ".path-replace-modal" in css
    assert ".path-replace-modal .preview-box" in css
    assert "max-height: min(560px, 58vh);" in css
    assert "resize: vertical;" in css
    assert "data-path-replace-dialog" in events_js


def test_v048_operation_generation_path_keeps_layout_and_offers_saved_paths():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "generationPathHistory: []" in state_js
    assert "generation_path_history" in persistence_js
    assert "addGenerationPathHistory" in actions_js
    assert "renderGenerationPathOptions" in render_operation_js
    assert 'list="generation-path-options"' not in render_operation_js
    assert '<datalist id="generation-path-options">' not in render_operation_js
    assert "renderGenerationPathDropdown" in render_operation_js
    assert "recordSuccessfulGenerationHistories(payload)" in actions_js
    assert 'event.target.name === "generation_path"' in events_js


def test_v049_settings_success_histories_and_custom_path_dropdown_exist():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "successfulProviderFieldHistory" in state_js
    assert "successful_provider_field_history" in persistence_js
    assert "addSuccessfulProviderFieldHistory" in actions_js
    assert "recordSuccessfulGenerationHistories" in actions_js
    assert "recordSuccessfulGenerationHistories(payload)" in actions_js
    assert "renderSettingHistoryInput" in render_settings_js
    assert 'renderSettingHistoryInput("api_key_env"' in render_settings_js
    assert 'renderSettingHistoryInput("model"' in render_settings_js
    assert 'renderSettingHistoryInput("user_agent"' in render_settings_js

    assert "renderGenerationPathDropdown" in render_operation_js
    assert 'list="generation-path-options"' not in render_operation_js
    assert "<datalist" not in render_operation_js
    assert "generation-path-dropdown" in render_operation_js
    assert "toggle-generation-path-dropdown" in events_js
    assert "select-generation-path-history" in events_js
    assert ".generation-path-dropdown" in css
    assert "width: max-content;" in css
    assert "max-width: min(920px, calc(100vw - 32px));" in css


def test_v061_settings_history_uses_shared_api_and_provider_config_sources():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_manager_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")
    config_py = (ROOT / "backend" / "config.py").read_text(encoding="utf-8")

    assert "providerFieldHistoryValues(field)" in render_settings_js
    assert "settingsSharedProviderFieldHistory" in render_settings_js
    assert "settingsProviderConfigFieldValues(field)" in render_settings_js
    assert 'api("/api/provider-field-history")' in actions_data_js
    assert 'api("/api/provider-field-history", {' in actions_manager_js
    assert "recordSuccessfulProviderFieldHistory" in actions_manager_js
    assert "loadProviderFieldHistory().catch(() => {})" in events_js
    assert "@api.get(\"/provider-field-history\")" in api_py
    assert "@api.post(\"/provider-field-history\")" in api_py
    assert "record_successful_provider_field_history(provider_config)" in api_py
    assert "provider_field_history" in config_py
    assert '"api_key"' not in config_py[config_py.find("PROVIDER_FIELD_HISTORY_FIELDS") : config_py.find("def normalize_provider_field_history")]


def test_v061_code_example_textareas_keep_dark_theme_even_when_readonly():
    css = read_frontend("styles.css")

    code_css = css[css.find(".code-example {") : css.find(".code-example-shell")]
    readonly_css = css[css.find(".code-example-editor[readonly]") : css.find(".custom-script-warning")]
    assert "background: #111827;" in code_css
    assert "color: #f8fafc;" in code_css
    assert "background: #111827;" in readonly_css
    assert "color: #f8fafc;" in readonly_css
    assert "background: #fff;" not in readonly_css


def test_v061_custom_script_outer_timeout_is_3600_seconds():
    runner_py = (ROOT / "backend" / "custom_script_runner.py").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")
    tests = (ROOT / "tests" / "test_custom_script_runner.py").read_text(encoding="utf-8")

    assert "CUSTOM_SCRIPT_TIMEOUT_SECONDS = 3600" in runner_py
    assert "timeout_seconds=CUSTOM_SCRIPT_TIMEOUT_SECONDS" in api_py
    assert "自定义代码执行超时（{timeout_seconds} 秒）" in runner_py
    assert "test_v061_custom_script_default_timeout_is_3600_seconds" in tests
    assert "== 900" not in tests


def test_v062_operation_adds_draft_instead_of_generating_directly():
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")

    operation_area = render_operation_js[
        render_operation_js.find("function renderOperationArea") :
        render_operation_js.find("Object.assign(globalThis")
    ]
    operation_input_images = render_operation_js[
        render_operation_js.find("function renderOperationInputImagesBlock") :
        render_operation_js.find("function renderGenerationPathOptions")
    ]
    operation_form_submit = events_js[
        events_js.rfind('const operationForm = event.target.closest("[data-operation-form]")') :
        events_js.rfind('const form = event.target.closest("[data-settings-form]")')
    ]
    generate_fn = actions_js[
        actions_js.find("async function generateFromOperation") :
        actions_js.find("async function resubmitInstance")
    ]
    batch_toolbar = render_save_js[
        render_save_js.find("function renderBatchToolbar") :
        render_save_js.find("function renderSaveArea")
    ]

    assert 'data-action="set-operation-mode"' not in operation_area
    assert "renderModeButton" not in operation_area
    assert "文生图" not in operation_area
    assert "图生图" not in operation_area
    assert "operation-input-placeholder" not in operation_input_images
    assert "shouldShowOperationInputImages()" not in operation_input_images
    assert 'data-action="add-operation-draft"' in operation_area
    assert ">新增</button>" in operation_area
    assert ">生成</button>" not in operation_area
    assert "addOperationDraft();" in operation_form_submit
    assert "api(\"/api/instances\"" in generate_fn
    assert "api(\"/api/generate\"" not in generate_fn
    assert "createPendingInstancesForTask" not in generate_fn
    assert "inferOperationModeFromInputs" in actions_js
    assert '"source": "manual"' in actions_js or 'source: "manual"' in actions_js
    assert 'data-action="new-manual-instance"' not in batch_toolbar


def test_v062_copy_submit_shortcuts_and_labels_use_prepare_then_submit_workflow():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]
    copy_fn = actions_js[
        actions_js.find("async function copySubmitInstance") :
        actions_js.find("async function retryFailedInstance")
    ]
    submit_fn = actions_js[
        actions_js.find("async function submitManualInstance") :
        actions_js.find("async function cancelGenerationTask")
    ]
    keydown_fn = events_js[
        events_js.find('document.addEventListener("keydown"') :
        events_js.find('document.addEventListener("paste"')
    ]

    assert "复制提交" not in instance_card
    assert "重新提交" not in instance_card
    assert ">复制</button>" in instance_card
    assert ">提交</button>" in instance_card
    assert ">重提</button>" in instance_card
    assert 'data-action="submit-manual-instance"' in instance_card
    assert "isPreparedInstance" in render_instance_js
    assert "已有输出图" in instance_card
    assert "api(\"/api/instances\"" in copy_fn
    assert "api(\"/api/generate\"" not in copy_fn
    assert "createPendingInstancesForTask" not in copy_fn
    assert "target_instance_id: Number(instanceId)" in submit_fn
    assert "markInstanceRunningInPlace" in submit_fn
    assert "createPendingInstancesForTask" not in submit_fn
    assert "submitSelectedInstances();" in keydown_fn
    assert "addOperationDraft();" in keydown_fn
    assert "generateFromOperation();" not in keydown_fn
    assert "!event.altKey" in events_js
    assert 'String(event.key || "").toLowerCase() !== "n"' in events_js


def test_v063_manager_uses_shared_eight_column_grid_and_left_status_area():
    variables_css = (ROOT / "frontend" / "css" / "00-variables.css").read_text(encoding="utf-8")
    operation_css = (ROOT / "frontend" / "css" / "04-operation.css").read_text(encoding="utf-8")
    instance_css = (ROOT / "frontend" / "css" / "06-instance-card.css").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")

    assert "--record-meta-col:" in variables_css
    assert "--record-prompt-col:" in variables_css
    assert "--record-input-col:" in variables_css
    assert "--record-size-col:" in variables_css
    assert "--record-output-col:" in variables_css
    assert "--record-detail-col:" in variables_css
    assert "--record-status-col:" in variables_css
    assert "--record-action-col:" in variables_css

    operation_grid = operation_css[
        operation_css.find(".operation-area.image-record") :
        operation_css.find(".operation-area .operation-mode-block")
    ]
    save_css = (ROOT / "frontend" / "css" / "05-save-area.css").read_text(encoding="utf-8")
    instance_grid = save_css[
        save_css.find(".save-list.is-single .instance-card.image-record") :
        save_css.find(".save-list.is-single .instance-card .instance-card-header")
    ]
    expected_columns = (
        "var(--record-meta-col) var(--record-prompt-col) "
        "var(--record-input-col) var(--record-size-col) "
        "var(--record-output-col) var(--record-detail-col) "
        "var(--record-status-col) var(--record-action-col)"
    )
    assert expected_columns in compact_css(operation_grid)
    assert expected_columns in compact_css(instance_grid)
    assert "--op-status-col" not in operation_grid
    assert ".operation-area.mode-text_to_image" not in operation_css
    status_panel_css = operation_css[
        operation_css.find(".operation-area .operation-status-panel") :
        operation_css.find(".operation-area .operation-actions")
    ]
    assert "grid-column: 1;" in status_panel_css
    assert "grid-row: 1;" in status_panel_css
    assert ".operation-area .operation-actions { grid-column: 8; }" in operation_css
    assert 'class="operation-status-panel"' in render_operation_js


def test_v063_running_database_instances_stay_in_formal_list_and_pending_section_only_has_temporary_items():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis", render_save_js.find("function renderSaveArea"))
    ]

    assert "const processInstances = mergePendingWithInstances(pendingInstances, runningInstances);" not in save_area
    assert "const processInstances = renderPendingProcessInstances(pendingInstances);" in save_area
    assert "!Number.isFinite(Number(item?.id))" in render_save_js
    assert "const formalInstances = realInstances;" in save_area
    assert "已有数据库实例的生成中状态保持在原列表位置" in save_area
    assert '<section class="pending-section">' in save_area


def test_v063_failed_instances_can_copy_and_submit_retry_buttons_align():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]

    failed_branch = instance_card[
        instance_card.find("failed", instance_card.find("const inlineActions"))
        :
        instance_card.find(": `", instance_card.find("failed", instance_card.find("const inlineActions")))
    ]
    assert "${copyAction}" in failed_branch
    assert "带入" in failed_branch
    assert "重提" in failed_branch
    assert "submit-instance-button" in failed_branch
    assert "instance-action-slot" in instance_card
    assert "instance-action-slot-spacer" in instance_card
    assert "data-action=\"delete-instance\"" in instance_card


def test_v064_operation_removes_title_and_moves_size_controls_to_output_column():
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    operation_css = (ROOT / "frontend" / "css" / "04-operation.css").read_text(encoding="utf-8")

    operation_area = render_operation_js[
        render_operation_js.find("function renderOperationArea") :
        render_operation_js.find("Object.assign(globalThis")
    ]
    operation_grid = operation_css[
        operation_css.find(".operation-area.image-record") :
        operation_css.find(".operation-area .record-input-images .image-grid")
    ]
    generation_options_css = operation_css[
        operation_css.find(".record-generation-options") :
        operation_css.find(".record-generation-options .field > span")
    ]
    status_css = operation_css[
        operation_css.find(".operation-status-panel") :
        operation_css.find(".operation-status-popover")
    ]

    assert "<span>操作区</span>" not in operation_area
    assert "operation-mode-block" not in operation_area
    assert ".operation-area .operation-mode-block" not in operation_css
    assert ".operation-area .operation-input-images { grid-column: 3 / 5; }" in operation_css
    assert ".operation-area .record-generation-options { grid-column: 5; }" in operation_css
    assert ".operation-area .record-detail { grid-column: 6 / 8; }" in operation_css
    assert ".operation-area .operation-actions { grid-column: 8; }" in operation_css
    status_panel_css = operation_css[
        operation_css.find(".operation-area .operation-status-panel") :
        operation_css.find(".operation-area .operation-actions")
    ]
    assert "grid-column: 1;" in status_panel_css
    assert "grid-row: 1;" in status_panel_css
    assert "grid-row: 1;" in status_css
    assert "padding-top: 22px;" not in generation_options_css
    assert "align-self: stretch;" in generation_options_css
    assert "var(--record-detail-top-row)" in generation_options_css
    assert "var(--operation-control-stack-height)" in generation_options_css
    assert "operation-status-tail" in render_operation_js
    assert "compactOperationStatusMessage(statusMessage)" not in render_operation_js
    assert "text-overflow: ellipsis;" in status_css
    assert "direction: rtl;" in status_css
    assert "white-space: nowrap;" in status_css


def test_v064_instance_status_badges_and_provider_editability_are_state_based():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")

    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]
    source_label_fn = render_instance_js[
        render_instance_js.find("function sourceLabel") :
        render_instance_js.find("function formatDate")
    ]
    provider_row_fn = render_instance_js[
        render_instance_js.find("function renderProviderSourceRow") :
        render_instance_js.find("function formatPendingElapsed")
    ]

    assert "function instanceStatusLabel" in render_instance_js
    assert "function instanceHasOutput" in render_instance_js
    assert "function canEditInstanceProvider" in render_instance_js
    assert '"准备"' in render_instance_js
    assert '"失败"' in render_instance_js
    assert '"生成"' in render_instance_js
    assert '"手动"' not in source_label_fn
    assert "sourceLabel(source)" not in provider_row_fn
    assert "instanceStatusLabel(item)" in provider_row_fn
    assert "canEditInstanceProvider(item)" in provider_row_fn
    assert 'source === "generated"' not in provider_row_fn
    assert 'instance.source === "generated" && instance.generation_size' not in instance_card
    assert "instance.generation_size" in instance_card


def test_v064_source_filter_options_use_instance_state_semantics():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    database_py = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")

    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis")
    ]

    assert 'name="source"' not in save_area
    assert "instance_state_where" in database_py
    assert "prepared" in database_py
    assert "generated" in database_py
    assert "COALESCE(output_image_path, '') <> ''" in database_py
    assert "COALESCE(output_image_path, '') = ''" in database_py


def test_v064_ctrl_enter_retries_failed_instances_and_reports_counts():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    submit_selected_fn = actions_js[
        actions_js.find("async function submitSelectedInstances") :
        actions_js.find("async function cancelGenerationTask")
    ]

    assert 'item.generation_status === "failed"' in submit_selected_fn
    assert "retryFailedInstance(id)" in submit_selected_fn
    assert "retried" in submit_selected_fn
    assert "已提交" in submit_selected_fn
    assert "已重提" in submit_selected_fn
    assert "跳过" in submit_selected_fn
    assert '|| item.generation_status === "failed"' not in submit_selected_fn


def test_v064_copy_instance_preserves_generation_size_fields_without_outputs():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    copy_fn = actions_js[
        actions_js.find("async function copySubmitInstance") :
        actions_js.find("async function retryFailedInstance")
    ]

    assert "copiedGenerationParams" in copy_fn
    assert "copiedGenerationSize" in copy_fn
    assert "generation_size: copiedGenerationSize" in copy_fn
    assert "resolved_size: copiedGenerationSize" in copy_fn
    assert "size: copiedGenerationSize" in copy_fn
    assert "ratio: options.ratio" in copy_fn
    assert "resolution_level: options.resolution_level" in copy_fn
    assert "n: options.n" in copy_fn
    assert "output_image_paths: []" in copy_fn
    assert 'output_image_path: ""' in copy_fn


def test_v049_save_card_removes_single_move_and_adds_select_zone_manual_submit():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]
    assert 'data-action="move-instance"' not in instance_card
    assert 'data-action="batch-move-instances"' in read_frontend("app.js")
    assert 'data-action="submit-manual-instance"' in instance_card
    assert "submitAction" in instance_card
    assert "复制" in instance_card
    assert "提交" in instance_card
    assert "data-action=\"toggle-select-zone\"" in instance_card
    assert "toggleSelectInstanceFromZone" in actions_js
    assert "submitManualInstance" in actions_js
    assert "instance?.output_image_path" in actions_js
    assert "已有输出图" in actions_js
    assert "api(\"/api/instances/" in actions_js
    assert 'action === "toggle-select-zone"' in events_js
    assert 'action === "submit-manual-instance"' in events_js
    assert ".instance-select-zone" in css


def test_v049_operation_removes_output_box_and_limits_status_height():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    lightbox_js = (ROOT / "frontend" / "js" / "lightbox.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    operation_area = render_operation_js[
        render_operation_js.find("function renderOperationArea") :
        render_operation_js.find("Object.assign(globalThis")
    ]
    assert "record-output-image" not in operation_area
    assert "choose-output-image" not in operation_area
    assert "output_image_path" not in state_js[state_js.find("const OPERATION_DEFAULTS") :]
    assert "output_image_path" not in persistence_js[persistence_js.find("function persistedOperationState") : persistence_js.find("function persistedSaveFilterState")]
    assert "var(--record-output-col)" in css[css.find(".operation-area.image-record") : css.find(".operation-area .operation-mode-block")]
    assert "--record-output-col" in css

    assert "compactOperationStatusMessage" in lightbox_js
    assert "operation-status-popover" in render_operation_js
    assert "title=\"${escapeHtml(statusMessage)}\"" in render_operation_js
    assert ".operation-status-panel" in css
    status_css = css[css.find(".operation-status-panel") : css.find(".operation-button-row")]
    assert "max-height: calc(var(--record-main-height) + 22px);" in status_css
    assert "overflow: hidden;" in status_css
    assert ".operation-status-panel:hover .operation-status-popover" in css


def test_v049_provider_key_expands_beyond_three_digits():
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")

    next_key_fn = actions_settings_js[
        actions_settings_js.find("function nextProviderKey") :
        actions_settings_js.find("function createProviderDraft")
    ]
    assert "provider_" in next_key_fn
    assert ".padStart(3" not in next_key_fn
    assert ".padStart(4" in next_key_fn or "Date.now()" in next_key_fn


def test_v049_dropdowns_close_on_outside_click_and_provider_switch():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "function closeFloatingDropdownsForClick" in events_js
    assert "state.generationPathDropdownOpen = false;" in events_js
    assert 'state.settingHistoryDropdownOpen = "";' in events_js
    assert "closeFloatingDropdownsForClick(event.target)" in events_js
    provider_start = events_js.find('if (event.target.name === "provider")')
    provider_change = events_js[
        provider_start :
        events_js.find('if (\n    event.target.name === "adapter"', provider_start)
    ]
    assert 'state.settingHistoryDropdownOpen = "";' in provider_change


def test_v049_escape_clears_save_area_selection():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")

    assert "function hasSelectedInstances" in actions_js
    assert "hasSelectedInstances" in actions_js[actions_js.find("Object.assign(globalThis") :]
    assert 'event.key === "Escape" && state.page === "manager" && hasSelectedInstances()' in events_js
    assert "clearCurrentPageSelection();" in events_js


def test_v049_settings_api_key_has_full_value_hover_title():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")

    api_key_field = render_settings_js[
        render_settings_js.find('<span>api_key</span>') :
        render_settings_js.find('<span>api_key_env</span>')
    ]
    assert 'name="api_key"' in api_key_field
    assert 'title="${escapeHtml(provider.api_key || "")}"' in api_key_field


def test_v049_pending_generation_section_has_no_process_title():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")

    pending_section = render_save_js[
        render_save_js.find('<section class="pending-section">') :
        render_save_js.find('<div class="save-list', render_save_js.find('<section class="pending-section">'))
    ]
    assert "过程区" not in pending_section
    assert "pending-label" not in pending_section


def test_v050_pending_instances_render_after_formal_save_list_without_affecting_pagination():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis", render_save_js.find("function renderSaveArea"))
    ]

    assert "const processInstances = renderPendingProcessInstances(pendingInstances);" in save_area
    assert "const cards = formalInstances.map((instance) => renderInstanceCard(instance)).join(\"\");" in save_area
    assert save_area.find('<div class="save-list') < save_area.find('<section class="pending-section">')
    assert "生成中实例不参与正式分页" in save_area


def test_v050_save_area_submits_use_source_provider_and_backend_request_provider():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    assert "function providerForInstanceSubmit(item)" in actions_js
    assert "const providerKey = providerForInstanceSubmit(item);" in actions_js
    assert "provider_key: providerKey," in actions_js
    assert "provider_key: activeProviderName()," in actions_js
    assert "def requested_provider_config(app_config: dict, requested_provider_key: str = \"\")" in api_py
    assert "requested_provider_key = str(data.get(\"provider_key\") or \"\").strip()" in api_py
    assert "provider_key, provider_config = requested_provider_config(app_config, requested_provider_key)" in api_py
    assert "active_provider_config(app_config)" in api_py


def test_v060_settings_code_area_has_param_intro_tab_and_inline_actions():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    code_tabs_fn = render_settings_js[
        render_settings_js.find("function renderCodeExampleTabs") :
        render_settings_js.find("function renderOpenAIProviderSettings")
    ]
    show_tab_fn = actions_settings_js[
        actions_settings_js.find("function showCodeExampleTab") :
        actions_settings_js.find("function editCodeExample")
    ]
    copy_fn = actions_settings_js[
        actions_settings_js.find("async function copyCodeExample") :
        actions_settings_js.find("async function saveCustomScript")
    ]

    assert 'data-code-tab="param-intro"' in code_tabs_fn
    assert "参数介绍" in code_tabs_fn
    assert "renderCodeExampleActions(displayCodeTab)" in code_tabs_fn
    assert "code-example-actions" not in code_tabs_fn[code_tabs_fn.find("code-example-panel") :]
    assert 'name="param_intro"' in code_tabs_fn
    assert "parameterIntroCode(provider, callMethod, exampleMode)" in code_tabs_fn
    assert 'tab === "param-intro"' in show_tab_fn
    assert 'activeTarget === "param-intro"' in copy_fn
    assert ".code-example-editor[readonly]" in css


def test_v060_parameter_intro_is_builtin_readonly_and_adapter_aware():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")

    assert "function parameterIntroCode" in render_settings_js
    intro_fn = render_settings_js[
        render_settings_js.find("function parameterIntroCode") :
        render_settings_js.find("function renderCodeExampleActions")
    ]
    assert "openai-google" in intro_fn
    assert "input_images" in intro_fn
    assert "response" in intro_fn
    assert "google" in intro_fn
    assert "other" in intro_fn
    assert "参数名" in intro_fn
    assert "默认值" in intro_fn
    assert "参数范围" in intro_fn
    assert "一般怎么选" in intro_fn


def test_v060_new_provider_starts_with_blank_connection_fields():
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")

    create_fn = actions_settings_js[
        actions_settings_js.find("function createProviderDraft") :
        actions_settings_js.find("async function cancelSettingsChanges")
    ]
    assert "blankProviderFieldDefaults()" in create_fn
    assert 'display_name: "",' in create_fn
    assert 'base_url: "",' in create_fn
    assert 'api_key: "",' in create_fn
    assert 'api_key_env: "",' in create_fn
    assert 'model: "",' in create_fn
    assert 'user_agent: "",' in create_fn
    assert 'proxy_url: "",' in create_fn
    assert '"新 Provider"' not in create_fn


def test_v060_copy_provider_creates_dirty_draft_without_changing_active_provider():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    settings_fn = render_settings_js[
        render_settings_js.find("function renderSettings") :
        render_settings_js.find("Object.assign(globalThis")
    ]
    copy_fn = actions_settings_js[
        actions_settings_js.find("function copyProviderDraft") :
        actions_settings_js.find("async function cancelSettingsChanges")
    ]

    assert 'data-action="copy-provider"' in settings_fn
    assert settings_fn.find('data-action="copy-provider"') < settings_fn.find('data-action="new-provider"')
    assert "function copyProviderDraft" in actions_settings_js
    assert "JSON.parse(JSON.stringify(currentProvider" in copy_fn
    assert "nextProviderKey(nextSettings.providers)" in copy_fn
    assert " 副本" in copy_fn
    assert "state.settingsProviderDraftIsNew = true;" in copy_fn
    assert "markSettingsDirty();" in copy_fn
    assert "active_provider" not in copy_fn
    assert 'if (action === "copy-provider")' in events_js
    assert "copyProviderDraft();" in events_js


def test_v050_pending_cancel_shows_cancelling_until_refresh():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")

    assert "item.cancelling = true;" in actions_js
    assert "item.cancelling = false;" in actions_js
    assert "item?.cancelling" in render_instance_js
    assert "取消中" in render_instance_js
    cancel_button = render_instance_js[
        render_instance_js.find('data-action="cancel-generation-task"') - 260 :
        render_instance_js.find('data-action="cancel-generation-task"') + 260
    ]
    assert "disabled" in cancel_button


def test_v050_settings_dirty_state_and_new_provider_first_save_are_stable():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "settingsDirty: false" in state_js
    assert "markSettingsDirty" in actions_settings_js
    assert "clearSettingsDirty" in actions_settings_js
    assert "state.settingsDirty = true;" in actions_settings_js
    assert "state.settingsDirty = false;" in actions_settings_js
    save_settings_fn = actions_settings_js[
        actions_settings_js.find("async function saveSettings") :
        actions_settings_js.find("async function changeOperationProvider")
    ]
    assert "syncSettingsProviderDraftFromForm(form);" in save_settings_fn
    assert "data-settings-dirty" in render_settings_js
    assert 'const saveDisabledAttr = saveDisabled;' in render_settings_js
    assert '${saveDisabledAttr}>保存设置</button>' in render_settings_js
    assert "markSettingsDirty();" in events_js


def test_v050_prompt_overlay_path_dropdown_and_shift_selection_polish():
    css = read_frontend("styles.css")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    prompt_overlay = css[css.find(".prompt-overlay") : css.find(".prompt-field.is-readonly:hover .prompt-overlay")]
    assert "padding: 7px 9px;" in prompt_overlay
    assert "32px" not in prompt_overlay
    dropdown_css = css[css.find(".generation-path-dropdown") : css.find(".generation-path-dropdown button")]
    assert "width: max-content;" in dropdown_css
    assert "max-width: min(920px, calc(100vw - 32px));" in dropdown_css
    assert "overflow-x: hidden;" in dropdown_css
    assert "if (event.shiftKey" in events_js
    select_block = events_js[
        events_js.find('action === "toggle-select-instance"') :
        events_js.find('action === "toggle-select-zone"')
    ]
    assert "event.preventDefault();" in select_block


def test_v0501_cancel_keeps_timer_and_defers_formal_result():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    pending_status_fn = render_instance_js[
        render_instance_js.find("function pendingStatusText") :
        render_instance_js.find("function pendingRetryLabel")
    ]
    cancel_fn = actions_js[
        actions_js.find("async function cancelGenerationTask") :
        actions_js.find("function instancePayload")
    ]
    cancel_endpoint = api_py[
        api_py.find('def api_cancel_generation') :
        api_py.find('@api.get("/tags")')
    ]

    assert "formatPendingElapsed(startedAtMs || item?.started_at_ms)" in pending_status_fn
    assert 'return "取消中";' not in pending_status_fn
    assert "state.cancellingGenerationTaskIds.add(cleanId);" in cancel_fn
    assert 'item.generation_error = "取消中";' not in cancel_fn
    assert 'item.generation_status = "failed";' not in cancel_fn
    assert "update_instance_generation_status" not in cancel_endpoint


def test_v0501_running_refresh_does_not_interrupt_active_manager_interactions():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    refresh_fn = actions_js[
        actions_js.find("function startRunningRefresh") :
        actions_js.find("function syncRunningRefresh")
    ]
    assert "managerInteractionUntil: 0" in state_js
    assert "function markManagerInteraction" in actions_js
    assert "markManagerInteraction," in actions_js
    assert "function shouldDeferRunningRefreshRender" in actions_js
    assert "if (!shouldDeferRunningRefreshRender())" in refresh_fn
    assert "state.runningRefreshNeedsRender = true;" in refresh_fn
    assert 'document.addEventListener("pointerdown"' in events_js
    assert "markManagerInteraction(event.target);" in events_js


def test_v0501_bring_in_does_not_change_provider_or_path():
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")

    apply_fn = actions_js[
        actions_js.find("async function applyBringInToOperation") :
        actions_js.find("async function bringInstanceToOperation")
    ]
    instance_fn = actions_js[
        actions_js.find("async function bringInstanceToOperation") :
        actions_js.find("async function bringHistoryToOperation")
    ]
    history_fn = actions_js[
        actions_js.find("async function bringHistoryToOperation") :
        actions_js.find("function operationPayload")
    ]

    assert "await changeOperationProvider" not in apply_fn
    assert "resolveBringInProvider" not in apply_fn
    assert "state.operation.generation_path = payload.generation_path" not in apply_fn
    assert "const preservedGenerationPath = state.operation.generation_path" in apply_fn
    assert "state.operation.generation_path = preservedGenerationPath" in apply_fn
    assert "provider_key:" not in instance_fn
    assert "generation_path:" not in instance_fn
    assert "provider_key:" not in history_fn
    assert "generation_path:" not in history_fn


def test_v0501_settings_cancel_button_and_delete_hotkey_exist():
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "async function cancelSettingsChanges" in actions_settings_js
    assert "state.settingsProviderDraftIsNew = false;" in actions_settings_js
    assert 'data-action="cancel-settings-changes"' in render_settings_js
    assert "${saveDisabledAttr}>取消</button>" in render_settings_js
    assert 'action === "cancel-settings-changes"' in events_js
    keydown_handler = events_js[events_js.find('document.addEventListener("keydown"'):]
    assert 'event.key === "Delete"' in keydown_handler
    assert "batchDeleteInstances();" in keydown_handler
    assert "hasBlockingSaveAreaKeyboardLayer()" in keydown_handler


def test_v0502_running_refresh_preserves_operation_interactions_and_refreshes_save_area_only():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    refresh_fn = actions_js[
        actions_js.find("function startRunningRefresh") :
        actions_js.find("function syncRunningRefresh")
    ]
    defer_fn = actions_js[
        actions_js.find("function shouldDeferRunningRefreshRender") :
        actions_js.find("function stopRunningRefresh")
    ]

    assert "instanceListRequestSeq: 0" in state_js
    assert "savePageNavigationUntil: 0" in state_js
    assert "function refreshSaveAreaOnly" in actions_js
    assert "refreshSaveAreaOnly();" in refresh_fn
    assert "renderManagerIfActive();" not in refresh_fn
    assert "document.activeElement" in defer_fn
    assert '.matches?.("button, select, input, textarea, [data-action]")' in defer_fn
    assert "state.savePageNavigationUntil" in defer_fn
    assert "markSavePageNavigation();" in actions_js
    assert "setSavePage(" in actions_js
    assert "markManagerInteraction(event.target);" in events_js


def test_v057_settings_provider_proxy_controls_exist():
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert 'proxy_mode: "system"' in providers_js
    assert 'proxy_url: ""' in providers_js
    assert "allow_untrusted_proxy_certificate: true" in providers_js
    assert 'name="proxy_mode"' in render_settings_js
    assert 'renderSelectedOption("system", "系统代理"' in render_settings_js
    assert 'renderSelectedOption("custom", "自定义代理"' in render_settings_js
    assert 'renderSelectedOption("none", "不走代理"' in render_settings_js
    assert 'name="proxy_url"' in render_settings_js
    assert 'name="allow_untrusted_proxy_certificate"' in render_settings_js
    assert 'provider.proxy_mode === "custom" ? "" : "disabled"' in render_settings_js
    assert "proxy_mode: formData.get(\"proxy_mode\")" in actions_settings_js
    assert "proxy_url: formData.get(\"proxy_url\")" in actions_settings_js
    assert "allow_untrusted_proxy_certificate: formData.get(\"allow_untrusted_proxy_certificate\") === \"on\"" in actions_settings_js
    assert "connection-proxy-mode-field" in css
    assert "connection-proxy-url-field" in css


def test_v058_openai_google_adapter_settings_and_examples_exist():
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    assert '"openai-google":' in providers_js
    assert 'label: "openai-google"' in providers_js
    assert "implemented: true" in providers_js
    assert "settingsKind: \"openai-google\"" in providers_js
    assert 'google_role: "user"' in providers_js
    assert "google_max_tokens: 4096" in providers_js
    assert "google_stream: false" in providers_js
    assert "openaiGoogleScriptExamples" in state_js
    assert 'api("/api/openai-google-script-examples")' in actions_settings_js
    assert "switchedAdapter" in (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    assert "includeFixedCodeExample" not in (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    assert "Google API 参数" in render_settings_js
    assert "renderOpenAIGoogleProviderSettings" in render_settings_js
    assert 'name="google_role"' in render_settings_js
    assert 'name="google_max_tokens"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_temperature"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_top_p"' in render_settings_js
    assert 'name="google_stream"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_stop"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_presence_penalty"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_frequency_penalty"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_logit_bias"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_user"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_response_format"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_seen"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_tools"' in render_settings_js
    assert 'renderOpenAIGoogleOptionalInput("google_tool_choice"' in render_settings_js
    assert "GOOGLE_B2_TEXT_SCRIPT" in api_py
    assert "GOOGLE_B2_IMAGE_SCRIPT" in api_py


def test_v059_fixed_code_examples_are_shared_readonly_and_not_provider_saved():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    fixed_fn = render_settings_js[
        render_settings_js.find("function fixedCodeExample") :
        render_settings_js.find("function customScriptCode")
    ]
    assert "providerCodeValue" not in fixed_fn
    assert "code_examples" not in fixed_fn
    assert "return defaultCodeExample(callMethod, exampleMode);" in fixed_fn

    tabs_fn = render_settings_js[
        render_settings_js.find("function renderCodeExampleTabs") :
        render_settings_js.find("function renderOpenAIProviderSettings")
    ]
    fixed_panel = tabs_fn[
        tabs_fn.find('data-code-panel="fixed-example"') :
        tabs_fn.find('data-code-panel="custom-code"')
    ]
    custom_panel = tabs_fn[tabs_fn.find('data-code-panel="custom-code"') :]
    assert 'name="fixed_code_example"' in fixed_panel
    assert "readonly" in fixed_panel
    assert 'data-action="edit-code-example"' not in fixed_panel
    assert 'data-action="save-code-example"' not in fixed_panel
    assert 'data-action="cancel-code-example"' not in fixed_panel
    assert 'data-code-target="fixed-example"' in render_settings_js
    assert 'data-action="edit-code-example"' in render_settings_js
    assert 'data-action="save-code-example"' in render_settings_js
    assert 'data-action="cancel-code-example"' in render_settings_js
    assert 'data-action="clear-custom-script"' in render_settings_js

    assert '"fixed_code_example"' not in actions_settings_js
    assert 'event.target.name === "fixed_code_example"' not in events_js
    assert "includeFixedCodeExample" not in events_js


def test_v059_openai_google_optional_params_show_none_placeholder_and_empty_semantics():
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "function renderOpenAIGoogleOptionalInput" in render_settings_js
    assert 'placeholder="None"' in render_settings_js
    assert "openai-google-none-input" in render_settings_js
    assert ".openai-google-none-input" in css
    assert "googleFormOptionalValue" in actions_settings_js
    assert '.toLowerCase() === "none"' in actions_settings_js
    for name in [
        "google_temperature",
        "google_top_p",
        "google_stop",
        "google_presence_penalty",
        "google_frequency_penalty",
        "google_logit_bias",
        "google_user",
        "google_response_format",
        "google_seen",
        "google_tools",
        "google_tool_choice",
    ]:
        assert f'renderOpenAIGoogleOptionalInput("{name}"' in render_settings_js
        assert f'googleFormOptionalValue(formData, "{name}")' in actions_settings_js
    assert "openai-google-user-agent-field" in render_settings_js
    assert 'inputClass: normalizeProviderAdapter(provider.adapter) === "openai-google" ? "openai-google-none-input" : ""' in render_settings_js


def test_v059_operation_disables_size_controls_for_openai_google_and_keeps_custom_size_visible():
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "function isActiveOpenAIGoogleProvider" in render_operation_js
    assert "openai-google-size-disabled" in render_operation_js
    assert "isActiveOpenAIGoogleProvider()" in render_operation_js
    assert ">无<" in render_operation_js
    assert 'title="无"' in render_operation_js
    assert "state.operation.generation_clarity === \"custom\"" in render_operation_js
    assert "state.operation.generation_size || state.operation.custom_generation_size" in render_operation_js
    assert "if (isActiveOpenAIGoogleProvider())" in events_js


def test_v059_generation_path_history_uses_shared_api_and_path_input_scrolls_to_end():
    actions_manager_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")
    database_py = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert 'api("/api/generation-path-history")' in actions_data_js
    assert 'api("/api/generation-path-history", {' in actions_manager_js
    assert 'loadGenerationPathHistory().catch(() => {})' in events_js
    assert "@api.get(\"/generation-path-history\")" in api_py
    assert "@api.post(\"/generation-path-history\")" in api_py
    assert "list_successful_generation_paths" in database_py
    assert "function scrollGenerationPathInputToEnd" in render_operation_js
    assert ".generation-path-input" in render_operation_js
    assert ".generation-path-dropdown" in css
    assert "max-width: min(" in css


def test_v0502_operation_status_panel_cannot_squeeze_detail_column():
    css = read_frontend("styles.css")
    variables_css = (ROOT / "frontend" / "css" / "00-variables.css").read_text(encoding="utf-8")
    operation_css = (ROOT / "frontend" / "css" / "04-operation.css").read_text(encoding="utf-8")
    responsive_css = (ROOT / "frontend" / "css" / "13-responsive.css").read_text(encoding="utf-8")

    assert "--record-status-col: 72px;" in variables_css
    assert "--record-status-col: 72px;" in responsive_css
    status_panel_css = operation_css[
        operation_css.find(".operation-status-panel") :
        operation_css.find(".operation-status-row")
    ]
    assert "width: 100%;" in status_panel_css
    assert "min-width: 0;" in status_panel_css
    assert "overflow: visible;" in status_panel_css
    assert ".operation-status-popover" in css


def test_v0502_history_records_group_retry_attempts_and_error_buttons():
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    database_py = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")

    assert "retry_records" in database_py
    assert "parent_history_id" in database_py
    assert "retry_attempt" in database_py
    assert "function renderHistoryErrorButtons" in render_history_js
    assert "错误${index + 1}" in render_history_js
    assert "historyVisibleErrorText(error.error_message || \"\")" in render_history_js
    assert "historyFieldCopyText(record, field)" in actions_js
    assert "field.startsWith(\"error:\")" in actions_js


def test_v048_tag_management_actions_move_to_context_menu():
    render_tag_js = (ROOT / "frontend" / "js" / "render-tag-management.js").read_text(encoding="utf-8")
    actions_tag_js = (ROOT / "frontend" / "js" / "actions-tag-management.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    card_template = render_tag_js[
        render_tag_js.find("const cards = items.map") :
        render_tag_js.find("return `", render_tag_js.find("const cards = items.map"))
    ]
    assert 'data-tag-management-context-id' in card_template
    assert 'data-action="rename-tag-management"' not in card_template
    assert 'data-action="open-merge-tag-management"' not in card_template
    assert "renderTagManagementContextMenu" in render_tag_js
    assert "tagManagementContextMenu" in actions_tag_js
    assert "openTagManagementContextMenu" in actions_tag_js
    assert "closeTagManagementContextMenu" in actions_tag_js
    assert 'data-action="rename-tag-management"' in render_tag_js
    assert 'data-action="open-merge-tag-management"' in render_tag_js
    assert "openTagManagementContextMenu" in events_js
    assert ".tag-management-context-menu" in css


def test_v051_save_toolbar_provider_filter_sort_and_path_replace_position():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")

    batch_toolbar = render_save_js[
        render_save_js.find("function renderBatchToolbar") :
        render_save_js.find("function renderInstanceThumbnailTile")
    ]
    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis")
    ]

    assert 'provider: "all"' in state_js
    assert 'select name="provider"' in save_area
    assert "Provider 筛选" not in save_area
    assert "<span>Provider</span>" in save_area
    main_row = save_area[save_area.find("save-toolbar-main-row") : save_area.find("save-toolbar-filter-row")]
    filter_row = save_area[save_area.find("save-toolbar-filter-row") : save_area.find("</form>")]
    assert 'name="sort"' in main_row
    assert 'name="provider"' in filter_row
    assert filter_row.find('name="provider"') < filter_row.find('name="mode_filter"')
    assert 'renderSelectedOption("provider_asc", "Provider A-Z", state.filters.sort)' in save_area
    assert 'renderSelectedOption("provider_desc", "Provider Z-A", state.filters.sort)' in save_area
    assert 'data-action="path-replace"' not in save_area[: save_area.find("${renderBatchToolbar()}")]
    assert batch_toolbar.find('data-action="toggle-thumbnail-view"') < batch_toolbar.find('data-action="path-replace"')
    assert 'params.set("provider", state.filters.provider || "all");' in actions_data_js
    assert "state.filters.provider = form.elements.provider?.value || \"all\";" in actions_js


def test_v051_instance_card_moves_clear_tags_next_to_bring_in():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    render_operation_js = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    tag_selector = render_operation_js[
        render_operation_js.find("function renderTagSelector") :
        render_operation_js.find("function renderSizePicker")
    ]
    instance_card = render_instance_js[
        render_instance_js.find("function renderInstanceCard") :
        render_instance_js.find("function renderInstanceTagEditor")
    ]
    inline_actions = instance_card[
        instance_card.find("const inlineActions") :
        instance_card.find("return `", instance_card.find("const inlineActions"))
    ]

    assert 'data-action="clear-tag-selector"\n        data-scope="${escapeHtml(scope)}"' in tag_selector
    assert 'scope !== "instance"' in tag_selector
    assert 'data-action="clear-instance-tags"' in instance_card
    assert 'title="清除标签"' in instance_card
    assert ">X</button>" in instance_card
    assert inline_actions.find("${clearTagsAction}") < inline_actions.find('data-action="bring-instance-to-operation"')
    assert ".instance-clear-tags-chip" in css


def test_v051_provider_dropdowns_use_unified_sorted_entries():
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")

    assert "function sortedProviderEntries" in providers_js
    assert "providerSortLabel" in providers_js
    assert "sortedProviderEntries()" in providers_js
    assert "Object.entries(providers)" not in providers_js[providers_js.find("function providerOptionsSelect") : providers_js.find("function instanceProviderText")]
    assert "Object.keys(providers)" not in providers_js[providers_js.find("function renderOperationProviderSelect") : providers_js.find("function currentSaveLayout")]
    assert "sortedProviderEntries(providers)" in render_settings_js


def test_v051_history_filters_display_and_cleanup_buttons_are_removed():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    history_page = render_history_js[
        render_history_js.find("function renderHistoryPage") :
        render_history_js.find("Object.assign(globalThis")
    ]
    summary_fn = render_history_js[
        render_history_js.find("function historySummaryText") :
        render_history_js.find("function renderHistoryRecord")
    ]

    assert 'model: "all"' in state_js
    assert 'size: "all"' in state_js
    assert 'mode: "all"' in state_js
    assert 'select name="history_size"' in history_page
    assert 'select name="history_mode"' in history_page
    assert 'select name="history_model"' in history_page
    assert "删除失败记录" not in history_page
    assert "删除日期之前记录" not in history_page
    assert 'type="submit" class="primary">筛选</button>' not in history_page
    assert 'params.set("model", state.history.model || "all");' in actions_data_js
    assert 'params.set("size", state.history.size || "all");' in actions_data_js
    assert 'params.set("mode", state.history.mode || "all");' in actions_data_js
    assert 'params.set("save_sort", state.filters.sort || "created_desc");' in actions_data_js
    assert "state.history.model = form.elements.history_model?.value || \"all\";" in actions_js
    assert 'event.target.name === "history_model"' in events_js
    assert "historyProviderLabel" in render_history_js
    assert "providerDisplayName" in render_history_js
    assert '["model", params.model || ""]' in summary_fn
    assert "record.instance_number" in render_history_js
    assert ".history-record.is-success" in css
    assert ".history-record.is-failed" in css


def test_v052_save_toolbar_two_rows_and_new_backend_filters():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis")
    ]
    main_row = save_area[save_area.find("save-toolbar-main-row") : save_area.find("save-toolbar-filter-row")]
    filter_row = save_area[save_area.find("save-toolbar-filter-row") : save_area.find("</form>")]

    assert 'status: "all"' in state_js
    assert 'size: "all"' in state_js
    assert 'call_method: "all"' in state_js
    assert 'model: "all"' in state_js
    assert "filterOptions" in state_js[state_js.find("filters:") : state_js.find("instances:")]
    assert "save-toolbar-main-row" in save_area
    assert "save-toolbar-filter-row" in save_area
    assert main_row.find('name="q"') < main_row.find('name="sort"') < main_row.find('name="per_page"') < main_row.find('name="save_layout"')
    expected_order = [
        'toolbar-field-tags',
        'name="status"',
        'name="provider"',
        'name="size"',
        'name="mode_filter"',
        'name="call_method"',
        'name="model"',
    ]
    positions = [filter_row.find(token) for token in expected_order]
    assert all(position >= 0 for position in positions)
    assert positions == sorted(positions)
    for label in ["标签", "状态", "Provider", "尺寸", "模式", "调用方式", "model"]:
        assert label in filter_row
    assert 'name="source"' not in filter_row
    assert "<span>来源</span>" not in filter_row
    assert "标签筛选</span>" not in save_area
    assert "来源筛选" not in save_area
    assert "方式筛选" not in save_area
    assert "Provider 筛选" not in save_area
    assert 'params.append("statuses", status);' in actions_data_js
    assert 'params.set("size", state.filters.size || "all");' in actions_data_js
    assert 'params.set("call_method", state.filters.call_method || "all");' in actions_data_js
    assert 'params.set("model", state.filters.model || "all");' in actions_data_js
    assert "state.filters.statuses = normalizeSavedStatuses(state.filters.statuses, state.filters.status);" in actions_js
    assert 'state.filters.call_method = form.elements.call_method?.value || "all";' in actions_js
    assert '["mode_filter", "provider", "size", "call_method", "model", "sort", "per_page"]' in render_instance_js
    assert ".save-toolbar-main-row" in css
    assert ".save-toolbar-filter-row" in css


def test_v065_save_status_filter_replaces_source_filter():
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")

    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("Object.assign(globalThis")
    ]
    status_options = render_save_js[
        render_save_js.find("function renderSaveStatusFilterOptions") :
        render_save_js.find("function saveStatusFilterLabel")
    ]
    status_label = render_save_js[
        render_save_js.find("function saveStatusFilterLabel") :
        render_save_js.find("function saveFilterLabel")
    ]

    assert 'name="source"' not in save_area
    assert "toolbar-field-source" not in save_area
    assert "<span>来源</span>" not in save_area
    for value in ["running", "prepared", "failed", "generated", "other"]:
        assert f'["{value}", saveStatusFilterLabel("{value}")]' in status_options
    for label in ["准备", "生成", "失败", "生成中", "其他"]:
        assert f'return "{label}";' in status_label
    assert '"ready"' not in status_options
    assert "正常" not in status_label
    assert 'params.set("source"' not in actions_data_js
    assert 'form.elements.source' not in actions_js
    assert '"source", "mode_filter"' not in render_instance_js
    assert "savedFilters.source" not in persistence_js
    assert "state.filters.source = \"all\";" in persistence_js


def test_v065_instance_clear_tags_badges_and_pending_color_are_compact():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert "清标签" not in render_instance_js
    assert 'title="清除标签"' in render_instance_js
    assert ">X</button>" in render_instance_js
    assert "function instanceStatusClass" in render_instance_js
    assert 'source-badge ${escapeHtml(instanceStatusClass(item))}' in render_instance_js
    assert ".source-badge.is-prepared" in css
    assert ".source-badge.is-generated" in css
    assert ".source-badge.is-failed" in css
    pending_css = css[css.find(".instance-card.is-pending") : css.find(".provider-source-row")]
    assert "background:" in pending_css
    assert "#fff3e6" in pending_css or "#ffedd5" in pending_css
    clear_css = css[css.find(".instance-clear-tags-chip") : css.find(".tag-selector-clear")]
    assert "width: 24px;" in clear_css
    assert "min-width: 24px;" in clear_css
    assert "border-radius: 999px;" in clear_css
    assert ".instance-inline-actions .instance-clear-tags-chip" in clear_css


def test_v065_history_status_labels_are_generation_semantics():
    constants_js = (ROOT / "frontend" / "js" / "constants.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")

    status_label = render_history_js[
        render_history_js.find("function historyStatusLabel") :
        render_history_js.find("function historyStatusClass")
    ]
    status_options = render_history_js[
        render_history_js.find("function renderHistoryStatusOptions") :
        render_history_js.find("function formatDuration")
    ]

    assert 'const HISTORY_STATUS_OPTIONS = ["all", "success", "failed", "running", "other"];' in constants_js
    assert 'return "生成";' in status_label
    assert 'return "失败";' in status_label
    assert 'return "生成中";' in status_label
    assert 'return "其他";' in status_label
    assert "成功" not in status_label
    assert "准备" not in status_options
    assert '["success", historyStatusLabel("success")]' in status_options
    assert '["failed", historyStatusLabel("failed")]' in status_options
    assert '["running", historyStatusLabel("running")]' in status_options
    assert '["other", historyStatusLabel("other")]' in status_options


def test_v065_detail_columns_expand_right_without_moving_left_edge_and_input_clear_aligns():
    css = read_frontend("styles.css")
    operation_css = (ROOT / "frontend" / "css" / "04-operation.css").read_text(encoding="utf-8")
    save_css = (ROOT / "frontend" / "css" / "05-save-area.css").read_text(encoding="utf-8")
    image_css = (ROOT / "frontend" / "css" / "07-image-slot.css").read_text(encoding="utf-8")

    assert ".operation-area .record-detail" in operation_css
    assert "grid-column: 6 / 8;" in operation_css[operation_css.find(".operation-area .record-detail") :]
    assert ".save-list.is-single .instance-card .record-detail" in save_css
    assert "grid-column: 6 / 8;" in save_css[save_css.find(".save-list.is-single .instance-card .record-detail") :]
    assert ".image-field-header" in image_css
    image_header_css = image_css[image_css.find(".image-field-header") : image_css.find(".image-field-clear")]
    assert "display: flex;" in image_header_css
    assert "justify-content: space-between;" in image_header_css
    assert "width: 100%;" in image_header_css


def test_v052_history_toolbar_three_rows_tag_filter_and_h_number():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    history_page = render_history_js[
        render_history_js.find("function renderHistoryPage") :
        render_history_js.find("Object.assign(globalThis")
    ]
    main_row = history_page[history_page.find("history-toolbar-main-row") : history_page.find("history-toolbar-filter-row")]
    filter_row = history_page[history_page.find("history-toolbar-filter-row") : history_page.find("history-toolbar-date-row")]
    date_row = history_page[history_page.find("history-toolbar-date-row") : history_page.find("</form>")]

    assert 'tags: []' in state_js[state_js.find("history:") :]
    assert "history-toolbar-main-row" in history_page
    assert "history-toolbar-filter-row" in history_page
    assert "history-toolbar-date-row" in history_page
    assert main_row.find('name="history_q"') < main_row.find('data-action="refresh-history"')
    assert 'name="history_per_page"' not in main_row
    assert "history-right-tools" not in main_row
    expected_order = [
        'renderHistoryTagFilterDropdown()',
        'name="history_status"',
        'name="history_provider"',
        'name="history_size"',
        'name="history_mode"',
        'name="history_call_method"',
        'name="history_model"',
    ]
    positions = [filter_row.find(token) for token in expected_order]
    assert all(position >= 0 for position in positions)
    assert positions == sorted(positions)
    assert date_row.find('name="history_start_date"') < date_row.find('name="history_end_date"') < date_row.find('name="history_per_page"') < date_row.find("history-right-tools")
    assert "record.history_number_label" in render_history_js
    assert 'H${String(record.history_number || record.display_index || index + 1).padStart(4, "0")}' in render_history_js
    assert "#—" not in render_history_js
    assert 'params.append("tags", tag);' in actions_data_js[actions_data_js.find("function loadGenerationHistory") :]
    assert "toggleHistoryFilterTag" in actions_js
    assert 'action === "toggle-history-filter-tag"' in events_js
    assert ".history-toolbar-main-row" in css
    assert ".history-toolbar-filter-row" in css
    assert ".history-toolbar-date-row" in css


def test_v052_history_popover_scrolls_and_instance_tag_space_is_not_reserved():
    css = read_frontend("styles.css")

    popover_css = css[css.find(".history-popover") : css.find(".check-row")]
    instance_tag_css = css[css.find(".instance-card .tag-selector-input-wrap") :]

    assert "max-height: calc(100vh - 24px);" in popover_css
    assert "display: flex;" in popover_css
    assert "overflow-y: auto;" in popover_css
    assert ".instance-card .tag-selector-input-wrap" in css
    assert "padding-right: 4px;" in instance_tag_css
    assert ".instance-card .tag-selector-input-wrap input" in css
    assert "min-width: 28px;" in instance_tag_css


def test_v053_history_page_removes_title_and_moves_pagination_to_date_row():
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    history_page = render_history_js[
        render_history_js.find("function renderHistoryPage") :
        render_history_js.find("Object.assign(globalThis")
    ]
    main_row = history_page[history_page.find("history-toolbar-main-row") : history_page.find("history-toolbar-filter-row")]
    date_row = history_page[history_page.find("history-toolbar-date-row") : history_page.find("</form>")]
    history_css = css[css.find(".history-panel") : css.find(".history-record")]

    assert "<h1>历史记录</h1>" not in history_page
    assert 'data-action="refresh-history"' in main_row
    assert "history-right-tools" not in main_row
    assert date_row.find('name="history_start_date"') < date_row.find('name="history_end_date"') < date_row.find("history-right-tools")
    assert 'data-action="history-page-first"' in date_row
    assert 'data-action="history-page-last"' in date_row
    assert ".history-top-row" in history_css
    assert "align-items: stretch;" in history_css
    assert ".history-panel .message:empty" in css
    assert "min-height: 0;" in css[css.find(".history-panel .message:empty") : css.find(".history-list")]
    assert ".history-list" in history_css
    assert "gap: 4px;" in history_css


def test_v053_history_popover_uses_full_width_without_extra_scroll_gutter():
    css = read_frontend("styles.css")

    popover_css = css[css.find(".history-popover") : css.find(".check-row")]

    assert "box-sizing: border-box;" in popover_css
    assert "padding: 8px 10px;" in popover_css
    assert "min-width: 0;" in popover_css
    assert "width: 100%;" in popover_css
    assert "padding-right: 2px;" in popover_css
    assert "scrollbar-gutter" not in popover_css


def test_v053_provider_filter_dropdowns_share_operation_sort_order():
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")

    helper = providers_js[
        providers_js.find("function providerFilterOptionEntries") :
        providers_js.find("function activeProviderDisplayName")
    ]
    save_provider_options = render_save_js[
        render_save_js.find("function renderProviderFilterOptions") :
        render_save_js.find("function renderSaveStatusFilterOptions")
    ]
    history_provider_options = render_history_js[
        render_history_js.find("function renderHistoryProviderOptions") :
        render_history_js.find("function renderHistoryStatusOptions")
    ]

    assert "function providerFilterOptionEntries" in providers_js
    assert "for (const [providerName, provider] of sortedProviderEntries())" in helper
    assert "historicalValues.sort" in helper
    assert "providerSortLabel" in helper
    assert "providerFilterOptionEntries(" in save_provider_options
    assert "state.filters.filterOptions?.providers" in save_provider_options
    assert "providerFilterOptionEntries(" in history_provider_options
    assert "state.history.filterOptions?.providers" in history_provider_options
    assert '{ emptyLabel: "未记录" }' in history_provider_options
    assert "historySelectOptions(state.history.filterOptions?.providers" not in render_history_js


def test_v054_history_toolbar_moves_per_page_to_pagination_and_uses_multiselect_tags():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    history_page = render_history_js[
        render_history_js.find("function renderHistoryPage") :
        render_history_js.find("Object.assign(globalThis")
    ]
    main_row = history_page[history_page.find("history-toolbar-main-row") : history_page.find("history-toolbar-filter-row")]
    filter_row = history_page[history_page.find("history-toolbar-filter-row") : history_page.find("history-toolbar-date-row")]
    date_row = history_page[history_page.find("history-toolbar-date-row") : history_page.find("</form>")]
    history_right_tools = date_row[date_row.find("history-right-tools") : date_row.find("</form>")]
    date_pagination_group = date_row[date_row.find("history-date-pagination-group") : date_row.find("history-right-tools")]

    assert "history_tag_dropdown_open" in state_js
    assert "renderHistoryTagFilterDropdown" in render_history_js
    assert "renderHistoryTagFilterDropdown()" in filter_row
    assert 'select name="history_tags"' not in render_history_js
    assert 'name="history_per_page"' not in main_row
    assert main_row.find('name="history_q"') < main_row.find('data-action="refresh-history"')
    assert date_row.find('name="history_start_date"') < date_row.find('name="history_end_date"') < date_row.find('name="history_per_page"') < date_row.find("history-right-tools")
    assert "history-per-page-field" in date_pagination_group
    assert 'name="history_per_page"' not in history_right_tools
    assert "history-tag-filter" in filter_row
    assert "history-tag-filter" in css
    assert "history-tag-filter.is-wide" in css
    assert "toggle-history-tag-filter-dropdown" in events_js
    assert "toggle-history-filter-tag" in events_js
    assert "clear-history-tag-filter" in events_js
    assert "state.history.tags = selectedHistoryTag" not in actions_js
    assert 'params.append("tags", tag);' in (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")


def test_v054_esc_closes_pinned_history_popover_after_higher_priority_layers():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")
    popover_css = css[css.find(".history-popover") : css.find(".history-popover-content")]

    assert "function hasPinnedHistoryTextPopover" in render_instance_js
    assert 'document.querySelector("[data-history-popover].is-pinned")' in render_instance_js
    lightbox_escape = events_js.find('if (event.key === "Escape" && state.lightbox.path)')
    node_escape = events_js.find('if (event.key === "Escape" && (state.nodeMenu?.openKey || state.nodeContextMenu?.open))')
    history_escape = events_js.find('if (event.key === "Escape" && hasPinnedHistoryTextPopover())')

    assert lightbox_escape >= 0
    assert node_escape >= 0
    assert history_escape >= 0
    assert lightbox_escape < history_escape
    assert node_escape < history_escape
    assert "closeHistoryTextPopover();" in events_js[history_escape : history_escape + 420]
    assert "let suppressHistoryPopoverHoverUntilLeave = false;" in events_js
    assert "suppressHistoryPopoverHoverUntilLeave = true;" in events_js
    assert 'historyPopoverSuppressHover === "true"' in events_js
    assert 'source.matches(":hover")' in events_js
    assert "pointer-events: none;" in popover_css
    assert ".history-popover.is-pinned" in css
    assert "pointer-events: auto;" in css[css.find(".history-popover.is-pinned") :]


def test_v054_node_dropdown_external_click_and_context_menu_rules():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    controls_fn = nodes_js[nodes_js.find("function renderNodeControls") : nodes_js.find("function openNodeNameDialog")]
    context_fn = nodes_js[nodes_js.find("function openNodeContextMenu") : nodes_js.find("function normalizeMoveNodePath")]
    click_handler = events_js[events_js.find('app.addEventListener("click"') : events_js.find('app.addEventListener("dragover"')]

    assert "<span>节点</span>" not in controls_fn
    assert "state.nodeMenu = { openKey: \"\" };" not in context_fn
    assert "!event.target.closest(\"[data-node-controls]\")" in click_handler
    assert "!event.target.closest(\"[data-node-context-menu]\")" in click_handler
    assert "closeNodeMenus();" in click_handler
    assert 'document.addEventListener("click", (event) =>' in events_js
    assert "node-controls-label" not in css


def test_v054_size_labels_use_fixed_mapping_for_save_and_history_filters():
    utils_js = (ROOT / "frontend" / "js" / "utils.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")

    assert "function presetSizePrefix" in utils_js
    assert "for (const [clarity, size] of Object.entries(sizes || {}))" in utils_js
    assert 'return prefix ? `${prefix}：${cleanSize}` : cleanSize;' in utils_js
    assert "renderSaveSizeFilterOptions" in render_save_js
    assert "formatPresetSizeLabel(value)" in render_save_js
    assert "renderHistorySizeOptions" in render_history_js
    assert "formatPresetSizeLabel(value)" in render_history_js
    assert '["Adapter", record.adapter || ""]' not in render_history_js
    assert '["尺寸", formatPresetSizeLabel(record.resolved_size || params.resolved_size || "")]' in render_history_js


def test_v055_size_filter_options_are_grouped_by_fixed_1k_2k_4k_mapping():
    utils_js = (ROOT / "frontend" / "js" / "utils.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")

    assert "const SIZE_GROUP_ORDER = [\"1K\", \"2K\", \"4K\"];" in utils_js
    assert "function presetSizeSortRank" in utils_js
    assert "function sortPresetSizeFilterValues" in utils_js
    assert "presetIndex" in utils_js
    assert "Number.MAX_SAFE_INTEGER" in utils_js
    assert "sortPresetSizeFilterValues(uniqueValues)" in render_save_js
    assert "sortPresetSizeFilterValues(uniqueValues)" in render_history_js
    assert "formatPresetSizeLabel(value)" in render_save_js
    assert "formatPresetSizeLabel(value)" in render_history_js


def test_v055_history_tag_filter_width_matches_save_tag_filter_and_dates_keep_full_width():
    css = read_frontend("styles.css")
    history_css = css[css.find(".history-panel") : css.find(".history-list")]
    tag_filter_css = css[css.find(".tag-filter {") : css.find(".tag-filter-control")]

    assert "--tag-filter-width" in tag_filter_css
    assert "width: var(--tag-filter-width);" in tag_filter_css
    assert "width: var(--tag-filter-width);" in history_css
    assert "flex: 0 0 var(--tag-filter-width);" in history_css
    assert ".history-select-field.history-tag-filter-field" in history_css
    assert ".history-date-field" in history_css
    assert "flex: 0 0 156px;" in history_css
    assert "min-width: 156px;" in history_css
    assert ".history-right-tools" in history_css
    assert "flex: 1 1 420px;" in history_css
    assert "justify-content: flex-end;" in history_css


def test_v055_node_dropdown_closes_from_capture_pointerdown_outside_boundaries():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")

    assert "function isNodeMenuInteractiveTarget" in events_js
    assert "function closeNodeMenusForOutsidePointerDown" in events_js
    assert 'document.addEventListener("pointerdown", closeNodeMenusForOutsidePointerDown, true);' in events_js
    assert 'target?.closest?.(".node-select-wrap")' in events_js
    assert 'target?.closest?.(".node-menu")' in events_js
    assert 'target?.closest?.("[data-node-context-menu]")' in events_js
    assert 'target?.closest?.("[data-node-name-dialog]")' in events_js


def test_v056_history_top_gap_alignment_and_tag_width_are_tightened():
    css = read_frontend("styles.css")
    variables_css = (ROOT / "frontend" / "css" / "00-variables.css").read_text(encoding="utf-8")
    history_css = css[css.find(".history-panel") : css.find(".history-record")]

    assert "--tag-filter-width: 320px;" in variables_css
    assert "gap: 4px;" in history_css
    assert ".history-right-tools" in history_css
    assert "align-items: end;" in history_css
    assert ".history-right-tools .toolbar-field" in history_css
    assert ".history-page-summary" in history_css
    assert "align-self: end;" in history_css
    assert ".history-list" in history_css
    assert "margin-top: 0;" in history_css


def test_v056_node_dropdown_blank_area_closes_and_real_nodes_are_draggable():
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    assert 'target?.closest?.(".node-select-wrap")' in events_js
    assert 'target?.closest?.(".node-menu")' in events_js
    assert 'target?.closest?.("[data-node-controls]")' not in events_js[
        events_js.find("function isNodeMenuInteractiveTarget") :
        events_js.find("function closeNodeMenusForOutsidePointerDown")
    ]
    assert 'draggable="true"' in nodes_js
    assert 'data-node-drag-id="${escapeHtml(node.id)}"' in nodes_js
    assert "function reorderSiblingNodes" in nodes_js
    assert "function handleNodeDragStart" in nodes_js
    assert "function handleNodeDrop" in nodes_js
    assert 'api("/api/nodes/reorder"' in nodes_js
    assert 'data-node-option-kind="new"' in nodes_js
    assert 'draggable="true"' not in nodes_js[
        nodes_js.find('data-node-option-kind="new"') :
        nodes_js.find('data-node-option-kind="all"')
    ]
    assert "dragstart" in events_js
    assert "drop" in events_js
    assert ".node-menu-option.is-dragging" in css
    assert ".node-menu-option.is-drop-target" in css








def test_v068_save_area_count_filter_and_prompt_title_polish():
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    lightbox_js = (ROOT / "frontend" / "js" / "lightbox.js").read_text(encoding="utf-8")
    css = read_frontend("styles.css")

    count_fn = render_instance_js[
        render_instance_js.find("function renderInstanceCount") :
        render_instance_js.find("function formatPendingElapsed")
    ]
    prompt_fn = (ROOT / "frontend" / "js" / "render-operation.js").read_text(encoding="utf-8")
    editable_prompt_fn = prompt_fn[
        prompt_fn.find("function renderEditablePromptField") :
        prompt_fn.find("function renderReadonlyPromptField")
    ]
    readonly_prompt_fn = prompt_fn[
        prompt_fn.find("function renderReadonlyPromptField") :
        prompt_fn.find("function renderPromptField")
    ]
    tag_dropdown = render_save_js[
        render_save_js.find("function renderTagFilterDropdown") :
        render_save_js.find("function renderModeFilterOptions")
    ]
    status_dropdown = render_save_js[
        render_save_js.find("function renderSaveStatusFilterDropdown") :
        render_save_js.find("function renderSaveStatusFilterOptions")
    ]
    save_area = render_save_js[
        render_save_js.find("function renderSaveArea") :
        render_save_js.find("function formatSource")
    ]

    assert '<input name="instance_generation_count"' in count_fn
    assert '<select name="instance_generation_count"' not in count_fn
    assert 'class="instance-count-input"' in count_fn
    assert 'inputmode="numeric"' in count_fn
    assert 'readonly' in count_fn
    assert 'validateInstanceGenerationCount' in actions_js
    assert '实例 ${instanceNumberLabel(item)} 的数量必须是正整数' in actions_js
    assert 'skippedInvalid.push' in actions_js
    assert 'function instanceGenerationCountInputValue(instanceId)' in actions_js
    assert 'validateInstanceGenerationCount(item, instanceGenerationCountInputValue(instanceId))' in actions_js
    assert 'validateInstanceGenerationCount(instance, instanceGenerationCountInputValue(instanceId))' in actions_js
    assert 'validateInstanceGenerationCount(draft || item, instanceGenerationCountInputValue(id))' in actions_js
    assert 'parseGenerationCount(countInput.value)' in lightbox_js

    assert 'field-title-action-slot field-title-clear-slot' in editable_prompt_fn
    assert 'field-title-action-slot field-title-copy-slot' in editable_prompt_fn
    assert 'field-title-action-slot field-title-count-slot' in editable_prompt_fn
    assert 'field-title-clear-placeholder' in readonly_prompt_fn
    assert editable_prompt_fn.find('field-title-clear-slot') < editable_prompt_fn.find('field-title-copy-slot') < editable_prompt_fn.find('field-title-count-slot')
    assert '.field-title-actions' in css
    assert 'grid-template-columns: 40px 40px 44px;' in css
    assert '.instance-count-input' in css
    count_input_css = css[css.find('.instance-count-input') : css.find('.instance-count-input') + 260]
    assert 'width: 38px;' in count_input_css

    assert 'data-action="clear-tag-filter"' not in tag_dropdown
    assert 'data-action="clear-save-status-filter"' not in status_dropdown
    assert 'class="filter-label-clear" data-action="clear-tag-filter"' in save_area
    assert 'class="filter-label-clear" data-action="clear-save-status-filter"' in save_area
    assert render_save_js.find('renderSelectedOption("number_desc", "编号 从大到小"') < render_save_js.find('renderSelectedOption("number_asc", "编号 从小到大"')
    assert render_save_js.find('renderSelectedOption("number_asc", "编号 从小到大"') < render_save_js.find('renderSelectedOption("created_desc", "最新优先"')
    assert 'grid-template-columns: minmax(0, 1fr) auto;' in css
    assert 'grid-template-columns: auto minmax(0, 1fr);' in css


def test_v068_history_number_type_filter_and_status_order():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    actions_data_js = (ROOT / "frontend" / "js" / "actions-data-safety.js").read_text(encoding="utf-8")
    actions_manager_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    api_py = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")
    database_py = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")

    status_options = render_history_js[
        render_history_js.find("function renderHistoryStatusOptions") :
        render_history_js.find("function formatDuration")
    ]
    history_page = render_history_js[
        render_history_js.find("function renderHistoryPage") :
        render_history_js.find("Object.assign(globalThis")
    ]
    filter_row = history_page[history_page.find("history-toolbar-filter-row") : history_page.find("history-toolbar-date-row")]

    assert 'number_type: "all"' in state_js
    assert status_options.find('["running", historyStatusLabel("running")]') < status_options.find('["failed", historyStatusLabel("failed")]')
    assert status_options.find('["failed", historyStatusLabel("failed")]') < status_options.find('["success", historyStatusLabel("success")]')
    assert status_options.find('["success", historyStatusLabel("success")]') < status_options.find('["other", historyStatusLabel("other")]')
    assert 'name="history_number_type"' in filter_row
    assert filter_row.find('name="history_model"') < filter_row.find('name="history_number_type"')
    assert 'renderHistoryNumberTypeOptions()' in filter_row
    assert 'params.set("number_type", state.history.number_type || "all")' in actions_data_js
    assert 'state.history.number_type = form.elements.history_number_type?.value || "all"' in actions_manager_js
    assert 'event.target.name === "history_number_type"' in events_js
    assert '"number_type": request.args.get("number_type", "all")' in api_py
    assert 'history_number_type_condition' in database_py
    assert 'json_extract(params_json, ' in database_py


def test_v068_setting_history_selection_marks_dirty_only_when_value_changes():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    select_block = events_js[
        events_js.find('if (action === "select-setting-history")') :
        events_js.find('if (action === "show-code-example-tab")')
    ]

    assert 'const previousValue = input.value;' in select_block
    assert 'if (value !== previousValue)' in select_block
    assert 'markSettingsDirty();' in select_block
    assert 'syncSettingsProviderDraftFromForm(form);' in select_block
    assert 'state.settingHistoryDropdownOpen = "";' in select_block


def test_v069_filter_space_tag_grid_node_and_history_layout_polish():
    save_css = (ROOT / "frontend" / "css" / "05-save-area.css").read_text(encoding="utf-8")
    tag_css = (ROOT / "frontend" / "css" / "13-tag-management.css").read_text(encoding="utf-8")
    history_css = (ROOT / "frontend" / "css" / "09-history.css").read_text(encoding="utf-8")
    history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    nodes_js = (ROOT / "frontend" / "js" / "nodes.js").read_text(encoding="utf-8")

    tag_toggle_css = save_css[save_css.find(".tag-filter-toggle") : save_css.find(".tag-filter-chip")]
    tag_option_css = save_css[save_css.find(".tag-filter-option") : save_css.find(".tag-filter-option.is-selected")]
    tag_check_css = save_css[save_css.find(".tag-filter-check") : save_css.find(".tag-filter-empty")]
    assert "padding-right: 30px;" not in tag_toggle_css
    assert "padding-right: 8px;" in tag_toggle_css
    assert "margin-left: auto;" in tag_check_css
    assert "width: 12px;" in tag_check_css
    assert "gap: 4px;" in tag_option_css

    assert "grid-template-columns: repeat(8, minmax(0, 1fr));" in tag_css
    assert ".node-menu-option.is-draggable" in save_css
    assert "cursor: grab;" in save_css
    assert "node-menu-drag-handle" in nodes_js
    assert 'class="node-menu-option is-draggable${selectedClass("node", node.id)}"' in nodes_js
    assert "is-draggable" not in nodes_js[
        nodes_js.find('class="node-menu-option is-create"') :
        nodes_js.find('data-node-option-kind="all"')
    ]

    date_row = history_js[
        history_js.find("history-toolbar-date-row") :
        history_js.find("history-page-summary")
    ]
    assert date_row.find("history_end_date") < date_row.find("history_per_page")
    assert date_row.find("history_per_page") < date_row.find("history-right-tools")
    assert ".history-date-pagination-group" in history_css
    assert ".history-per-page-field" in history_css


def test_v069_escape_edit_and_history_keyboard_paging_handlers():
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    actions_manager_js = (ROOT / "frontend" / "js" / "actions-manager.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")

    keydown_handler = events_js[events_js.find('document.addEventListener("keydown"') :]
    assert "function cancelAllEditingInstances" in actions_manager_js
    cancel_all_fn = actions_manager_js[
        actions_manager_js.find("function cancelAllEditingInstances") :
        actions_manager_js.find("async function saveInstanceDraft")
    ]
    assert "state.editing.clear();" in cancel_all_fn
    assert "function handleEscapeEditingInstances(event)" in events_js
    assert "handleEscapeEditingInstances(event)" in keydown_handler
    assert keydown_handler.find("hasPinnedHistoryTextPopover()") < keydown_handler.find("handleEscapeEditingInstances(event)")
    assert keydown_handler.find("handleEscapeEditingInstances(event)") < keydown_handler.find("hasSelectedInstances()")
    assert "handleHistoryKeyboardPaging(event)" in keydown_handler
    assert keydown_handler.find("switchLightboxImage(1)") < keydown_handler.find("handleHistoryKeyboardPaging(event)")

    history_paging_fn = events_js[
        events_js.find("function handleHistoryKeyboardPaging(event)") :
        events_js.find('document.addEventListener("pointerdown"', events_js.find("function handleHistoryKeyboardPaging(event)"))
    ]
    assert 'state.page !== "history"' in history_paging_fn
    assert "event.isComposing" in history_paging_fn
    assert "isHistoryKeyboardTextTarget(event.target)" in history_paging_fn
    assert "hasBlockingHistoryKeyboardLayer()" in history_paging_fn
    assert 'event.key === "ArrowLeft"' in history_paging_fn
    assert 'event.key === "ArrowRight"' in history_paging_fn
    assert "changeHistoryPage(-1)" in history_paging_fn
    assert "changeHistoryPage(1)" in history_paging_fn
    assert "record.history_number_label" in render_history_js


def test_v070_operation_provider_marker_dropdown_is_local_and_isolated():
    state_js = (ROOT / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    events_js = (ROOT / "frontend" / "js" / "events.js").read_text(encoding="utf-8")
    render_save_js = (ROOT / "frontend" / "js" / "render-save.js").read_text(encoding="utf-8")
    render_history_js = (ROOT / "frontend" / "js" / "render-history.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    render_instance_js = (ROOT / "frontend" / "js" / "render-instance.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "06-instance-card.css").read_text(encoding="utf-8")

    operation_provider_fn = providers_js[
        providers_js.find("function renderOperationProviderSelect") :
        providers_js.find("function currentSaveLayout")
    ]
    provider_options_fn = providers_js[
        providers_js.find("function providerOptionsSelect") :
        providers_js.find("function instanceProviderText")
    ]
    click_handler = events_js[
        events_js.find('app.addEventListener("click"') :
        events_js.find('app.addEventListener("contextmenu"')
    ]
    change_handler = events_js[
        events_js.find('app.addEventListener("change"') :
        events_js.find('app.addEventListener("input"')
    ]
    escape_handler = events_js[events_js.find('document.addEventListener("keydown"') :]

    assert "providerMarkers" in state_js
    assert "provider_dropdown_open" in state_js
    assert "provider_markers" in persistence_js
    assert "persistedProviderMarkers" in persistence_js
    assert "state.providerMarkers" in persistence_js
    assert "providerMarkerState" in providers_js
    assert "toggleProviderMarker" in providers_js
    assert "renderProviderMarkerBadge" in providers_js

    assert '<select name="operation_provider"' not in operation_provider_fn
    assert 'data-action="toggle-operation-provider-dropdown"' in operation_provider_fn
    assert 'data-action="select-operation-provider"' in operation_provider_fn
    assert "renderProviderMarkerBadge(providerName)" in operation_provider_fn
    assert 'data-action="toggle-operation-provider-marker"' in providers_js
    assert 'class="operation-provider-marker' in providers_js
    assert 'aria-expanded="${state.operation.provider_dropdown_open ? "true" : "false"}"' in operation_provider_fn
    assert "renderProviderMarkerBadge(selectedProvider, { button: false })" in operation_provider_fn

    assert 'if (action === "toggle-operation-provider-dropdown")' in click_handler
    assert 'if (action === "select-operation-provider")' in click_handler
    assert 'if (action === "toggle-operation-provider-marker")' in click_handler
    marker_click_block = click_handler[
        click_handler.find('if (action === "toggle-operation-provider-marker")') :
        click_handler.find('if (action === "toggle-thumbnail-view")')
    ]
    assert "event.stopPropagation();" in marker_click_block
    assert "toggleProviderMarker(actionNode.dataset.providerKey || \"\")" in marker_click_block
    assert "const providerChanged = providerKey && providerKey !== activeProviderName();" in click_handler
    assert "closeOperationProviderDropdown({ render: !providerChanged });" in click_handler
    assert "changeOperationProvider(providerKey)" in click_handler
    assert 'event.target.name === "operation_provider"' not in change_handler

    assert "state.operation.provider_dropdown_open" in events_js
    assert "operation-provider-select" in events_js
    assert "closeOperationProviderDropdown" in events_js
    assert "state.operation.provider_dropdown_open = false;" in escape_handler

    assert "operation-provider-marker" in css
    assert ".operation-provider-marker.is-checked" in css
    assert ".operation-provider-marker.is-rejected" in css
    assert ".operation-provider-dropdown" in css
    assert ".operation-provider-option" in css

    assert 'data-action="toggle-operation-provider-marker"' not in provider_options_fn
    assert 'data-action="toggle-operation-provider-marker"' not in render_save_js
    assert 'data-action="toggle-operation-provider-marker"' not in render_history_js
    assert 'data-action="toggle-operation-provider-marker"' not in render_settings_js
    assert 'data-action="toggle-operation-provider-marker"' not in render_instance_js


def test_v0701_operation_provider_dropdown_has_opaque_background():
    css = (ROOT / "frontend" / "css" / "06-instance-card.css").read_text(encoding="utf-8")
    dropdown_block = css[
        css.find(".operation-provider-dropdown {") :
        css.find(".operation-provider-option {")
    ]

    assert ".operation-provider-dropdown {" in dropdown_block
    assert "background: #fff;" in dropdown_block
    assert "box-shadow:" in dropdown_block


def test_v071_new_shared_adapters_and_provider_marker_tristate():
    providers_js = (ROOT / "frontend" / "js" / "providers.js").read_text(encoding="utf-8")
    render_settings_js = (ROOT / "frontend" / "js" / "render-settings.js").read_text(encoding="utf-8")
    actions_settings_js = (ROOT / "frontend" / "js" / "actions-settings.js").read_text(encoding="utf-8")
    persistence_js = (ROOT / "frontend" / "js" / "persistence.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "06-instance-card.css").read_text(encoding="utf-8")

    assert '"sysrv-google"' in providers_js
    assert '"apimart-openai"' in providers_js
    assert 'settingsKind: "sysrv-google"' in providers_js
    assert 'settingsKind: "apimart-openai"' in providers_js
    assert "supportsImageToImage: true" in providers_js
    assert "supportsCount: true" in providers_js

    assert "renderSysrvGoogleProviderSettings" in render_settings_js
    assert "renderApimartOpenAIProviderSettings" in render_settings_js
    assert 'normalizeProviderAdapter(provider.adapter) === "sysrv-google"' in render_settings_js
    assert 'normalizeProviderAdapter(provider.adapter) === "apimart-openai"' in render_settings_js
    assert "Google API 参数" in render_settings_js
    assert "Openai API 参数" in render_settings_js
    assert "request_timeout_seconds" in render_settings_js
    assert "download_timeout_seconds" in render_settings_js
    assert "max_retry_attempts" in render_settings_js
    assert "apimart_task_timeout_seconds" in render_settings_js
    assert "apimart_task_poll_interval_seconds" in render_settings_js
    assert "input_fidelity" in render_settings_js
    assert "mask_path" in render_settings_js
    assert "moderation" in render_settings_js

    assert "state.sysrvGoogleScriptExamples" in render_settings_js
    assert "state.apimartOpenAIScriptExamples" in render_settings_js
    assert "loadSharedScriptExamples" in actions_settings_js
    assert "/api/shared-script-examples" in actions_settings_js

    assert '["checked", "unused", "rejected"]' in persistence_js
    assert "providerMarkerState(key) === \"checked\"" in providers_js
    assert "state.providerMarkers[key] = \"unused\";" in providers_js
    assert "delete state.providerMarkers[key];" in providers_js
    assert "providerMarkerLabel(marker)" in providers_js
    assert "marker === \"unused\" ? \"-\"" in providers_js
    assert ".operation-provider-marker.is-unused" in css

