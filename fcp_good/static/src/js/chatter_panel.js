/** @odoo-module **/

import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { session } from "@web/session";

const STORAGE_KEY = "flex_chatter_panel_state";
const DEFAULT_STATE = { hidden: false, widthPercent: 32 };
const MIN_PERCENT = 27;
const MAX_PERCENT = 48;
const DEFAULT_PERCENT = 32;
const MIN_READABLE_PX = 300;
const MIN_PREVIEW_WIDTH_PX = 160;

function clamp(value, minValue, maxValue) {
    return Math.min(Math.max(value, minValue), maxValue);
}

function getUserMode() {
    const mode = session?.flex_chatter_panel?.chatter_position || "responsive";
    return ["responsive", "bottom"].includes(mode) ? mode : "responsive";
}

function normalizeState(state) {
    const nextState = { ...DEFAULT_STATE, ...(state || {}) };
    if (!Number.isFinite(Number(nextState.widthPercent))) {
        nextState.widthPercent = DEFAULT_PERCENT;
    }
    nextState.widthPercent = clamp(
        Number(nextState.widthPercent) || DEFAULT_PERCENT,
        MIN_PERCENT,
        MAX_PERCENT
    );
    nextState.hidden = Boolean(nextState.hidden);
    return nextState;
}

function getState() {
    try {
        return normalizeState(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
    } catch {
        return normalizeState({});
    }
}

function saveState(state) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeState(state)));
}

function findFormView(root) {
    if (!(root instanceof Node)) {
        return null;
    }
    return root.closest?.(".o_form_view") || root.querySelector?.(".o_form_view");
}

function findRenderer(formView) {
    return formView?.querySelector(".o_form_renderer") || formView;
}

function findSheet(formView) {
    return formView?.querySelector(".o_form_sheet") || null;
}

function findSheetWrapper(formView) {
    return formView?.querySelector(".o_form_sheet_bg") || null;
}

function findAttachmentPreview(formView) {
    const renderer = findRenderer(formView);
    return renderer?.querySelector(".o_attachment_preview") || null;
}

function isAttachmentPreviewOpen(formView) {
    const preview = findAttachmentPreview(formView);
    if (!preview || !preview.isConnected) {
        return false;
    }

    const style = window.getComputedStyle(preview);
    if (
        style.display === "none" ||
        style.visibility === "hidden" ||
        preview.hidden
    ) {
        return false;
    }

    const rect = preview.getBoundingClientRect();
    return rect.width >= MIN_PREVIEW_WIDTH_PX && rect.height > 0;
}

function findSideContainer(formView) {
    if (!(formView instanceof Node)) {
        return null;
    }
    return formView.querySelector(
        ".o_FormRenderer_chatterContainerOuter, .o_FormRenderer_chatterContainer"
    );
}

function findActualChatter(formView) {
    if (!(formView instanceof Node)) {
        return null;
    }
    return formView.querySelector(
        ".o-mail-Form-chatter, .o-mail-ChatterContainer, .o_ChatterContainer"
    );
}

function rememberOriginalPlace(element) {
    if (!element || element.__fcpOriginalMarker) {
        return;
    }
    const marker = document.createComment("flex-chatter-panel-original-place");
    element.parentNode?.insertBefore(marker, element);
    element.__fcpOriginalMarker = marker;
}

function restoreOriginalPlace(element) {
    const marker = element?.__fcpOriginalMarker;
    if (!marker?.parentNode || element.parentNode === marker.parentNode) {
        return;
    }
    marker.parentNode.insertBefore(element, marker.nextSibling);
}

function restoreResponsivePlaces(sideContainer, actualChatter) {
    restoreOriginalPlace(sideContainer);
    restoreOriginalPlace(actualChatter);
}

function clearElementStyle(element) {
    if (!element) {
        return;
    }
    for (const property of [
        "display", "width", "minWidth", "maxWidth", "flex", "flexBasis",
        "order", "margin", "marginTop", "marginLeft", "marginRight",
        "padding", "paddingTop", "border", "borderTop", "overflow",
        "overflowX", "alignSelf"
    ]) {
        element.style[property] = "";
    }
    element.style.removeProperty("--fcp-width");
}

function clearCustomClasses(element) {
    element?.classList.remove(
        "fcp-is-hidden",
        "fcp-responsive-target",
        "fcp-bottom-chatter",
        "fcp-bottom-side-container",
        "fcp-responsive-renderer",
        "fcp-responsive-sheet",
        "fcp-preview-left-pane",
        "fcp-preview-right-pane",
        "fcp-preview-chatter"
    );
}

function clearControls(formView, sideContainer) {
    formView?.querySelectorAll(".fcp-toggle-btn, .fcp-resizer")
        .forEach((element) => element.remove());
    sideContainer?.querySelectorAll(".fcp-toggle-btn, .fcp-resizer")
        .forEach((element) => element.remove());
}

function clearLayout(formView, sideContainer, actualChatter) {
    const renderer = findRenderer(formView);
    const sheetWrapper = findSheetWrapper(formView);
    const sheet = findSheet(formView);
    const preview = findAttachmentPreview(formView);

    // Only clear inline styles from chatter nodes. Odoo's attachment preview may
    // own inline width/flex values on renderer/sheet nodes, so those must remain.
    for (const element of [sideContainer, actualChatter]) {
        clearElementStyle(element);
    }

    for (const element of [
        renderer, sheetWrapper, sheet, preview, sideContainer, actualChatter,
    ]) {
        clearCustomClasses(element);
    }

    formView?.classList.remove("fcp-preview-open");
    formView?.style.removeProperty("--fcp-preview-width");
    formView?.style.removeProperty("--fcp-preview-toggle-right");
    formView?.style.removeProperty("--fcp-preview-toggle-left");
}

function applyBottomLayout(formView, sideContainer, actualChatter) {
    const sheet = findSheet(formView);
    if (!sheet || !actualChatter) {
        return;
    }

    restoreResponsivePlaces(sideContainer, actualChatter);
    rememberOriginalPlace(actualChatter);
    clearControls(formView, sideContainer);
    clearLayout(formView, sideContainer, actualChatter);

    if (actualChatter.parentNode !== sheet) {
        sheet.appendChild(actualChatter);
    }

    actualChatter.classList.add("fcp-bottom-chatter");
    actualChatter.style.width = "100%";
    actualChatter.style.minWidth = "0";
    actualChatter.style.maxWidth = "none";
    actualChatter.style.flex = "1 1 100%";

    if (sideContainer && sideContainer !== actualChatter) {
        sideContainer.classList.add("fcp-bottom-side-container");
        sideContainer.style.display = "none";
    }
}

function getResponsiveTarget(formView) {
    return findSideContainer(formView) || findActualChatter(formView);
}

function prepareResponsiveLayout(formView) {
    const renderer = findRenderer(formView);
    const sheetWrapper = findSheetWrapper(formView);

    renderer?.classList.add("fcp-responsive-renderer");
    sheetWrapper?.classList.add("fcp-responsive-sheet");
}

function getResponsiveWidth(formView, state) {
    const renderer = findRenderer(formView);
    const formWidth = renderer?.getBoundingClientRect().width ||
        formView.getBoundingClientRect().width || window.innerWidth;
    const percent = clamp(
        Number(state.widthPercent) || DEFAULT_PERCENT,
        MIN_PERCENT,
        MAX_PERCENT
    );

    const requestedPx = (formWidth * percent) / 100;
    const maxPx = (formWidth * MAX_PERCENT) / 100;
    const widthPx = Math.min(Math.max(requestedPx, MIN_READABLE_PX), maxPx);

    return {
        percent,
        px: Math.max(0, Math.round(widthPx)),
    };
}

function applySideWidth(formView, target, state) {
    if (!target) {
        return;
    }

    prepareResponsiveLayout(formView);
    const width = getResponsiveWidth(formView, state);

    target.classList.add("fcp-responsive-target");
    target.style.display = "";
    target.style.width = `${width.px}px`;
    target.style.minWidth = `${width.px}px`;
    target.style.maxWidth = `${width.px}px`;
    target.style.flex = `0 0 ${width.px}px`;
    target.style.flexBasis = `${width.px}px`;
    target.style.overflowX = "hidden";
}

function applyHiddenLayout(formView, target) {
    prepareResponsiveLayout(formView);
    if (!target) {
        return;
    }

    target.classList.add("fcp-is-hidden");
    target.style.display = "none";
}

function applyPreviewLayout(formView, target, state) {
    const sheetWrapper = findSheetWrapper(formView);
    const preview = findAttachmentPreview(formView);
    if (!sheetWrapper || !preview || !target) {
        return false;
    }

    prepareResponsiveLayout(formView);
    rememberOriginalPlace(target);

    if (target.parentNode !== sheetWrapper) {
        sheetWrapper.appendChild(target);
    }

    const previewWidth = Math.round(preview.getBoundingClientRect().width || 0);
    formView.classList.add("fcp-preview-open");
    formView.style.setProperty("--fcp-preview-width", `${previewWidth}px`);
    sheetWrapper.classList.add("fcp-preview-left-pane");
    preview.classList.add("fcp-preview-right-pane");
    target.classList.add("fcp-preview-chatter");

    // Position the chatter toggle from the actual left-pane edge instead of
    // relying on the preview width. Odoo's PDF preview may report a nested
    // viewer width that is smaller than the complete right pane.
    const formRect = formView.getBoundingClientRect();
    const leftPaneRect = sheetWrapper.getBoundingClientRect();
    const rightOffset = Math.max(0, Math.round(formRect.right - leftPaneRect.right));
    const leftOffset = Math.max(0, Math.round(leftPaneRect.left - formRect.left));
    formView.style.setProperty(
        "--fcp-preview-toggle-right",
        `${rightOffset + 8}px`
    );
    formView.style.setProperty(
        "--fcp-preview-toggle-left",
        `${leftOffset + 8}px`
    );

    target.querySelector(":scope > .fcp-resizer")?.remove();

    if (state.hidden) {
        target.classList.add("fcp-is-hidden");
        target.style.display = "none";
    } else {
        target.style.display = "";
        target.style.width = "100%";
        target.style.minWidth = "0";
        target.style.maxWidth = "100%";
        target.style.flex = "0 0 auto";
        target.style.flexBasis = "auto";
        target.style.alignSelf = "stretch";
        target.style.overflowX = "hidden";
    }

    return true;
}

function ensureToggleButton(formView) {
    let button = formView.querySelector(":scope > .fcp-toggle-btn");
    if (button) {
        return button;
    }

    button = document.createElement("button");
    button.type = "button";
    button.className = "fcp-toggle-btn";
    formView.appendChild(button);

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const state = getState();
        state.hidden = !state.hidden;
        saveState(state);
        applyFlexibleChatter(formView);
    });

    return button;
}

function ensureResizer(formView, target) {
    if (!target) {
        return null;
    }

    let resizer = target.querySelector(":scope > .fcp-resizer");
    if (resizer) {
        return resizer;
    }

    resizer = document.createElement("div");
    resizer.className = "fcp-resizer";
    target.prepend(resizer);

    let startX = 0;
    let startPercent = DEFAULT_PERCENT;
    let formWidth = 0;

    const onPointerMove = (ev) => {
        const state = getState();
        if (
            state.hidden ||
            getUserMode() === "bottom" ||
            isAttachmentPreviewOpen(formView) ||
            !formWidth
        ) {
            return;
        }

        const isRtl = document.documentElement.dir === "rtl";
        const deltaPx = isRtl ? ev.clientX - startX : startX - ev.clientX;
        const deltaPercent = (deltaPx / formWidth) * 100;
        state.widthPercent = clamp(startPercent + deltaPercent, MIN_PERCENT, MAX_PERCENT);
        saveState(state);
        applySideWidth(formView, target, state);
    };

    const onPointerUp = () => {
        document.body.classList.remove("fcp-resizing");
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("pointerup", onPointerUp);
    };

    resizer.addEventListener("pointerdown", (ev) => {
        const state = getState();
        if (
            state.hidden ||
            getUserMode() === "bottom" ||
            isAttachmentPreviewOpen(formView)
        ) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();

        startX = ev.clientX;
        startPercent = clamp(
            Number(state.widthPercent) || DEFAULT_PERCENT,
            MIN_PERCENT,
            MAX_PERCENT
        );
        formWidth = findRenderer(formView)?.getBoundingClientRect().width ||
            formView.getBoundingClientRect().width || window.innerWidth;

        document.body.classList.add("fcp-resizing");
        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerup", onPointerUp);
    });

    return resizer;
}

function updateToggle(button, state) {
    button.title = state.hidden ? "Show Chatter" : "Hide Chatter";
    button.setAttribute("aria-label", button.title);
    button.textContent = state.hidden ? "«" : "»";
}

function applyResponsiveLayout(formView, sideContainer, actualChatter, state) {
    restoreResponsivePlaces(sideContainer, actualChatter);
    clearLayout(formView, sideContainer, actualChatter);

    const target = getResponsiveTarget(formView);
    const toggle = ensureToggleButton(formView);
    const previewOpen = isAttachmentPreviewOpen(formView);

    if (previewOpen && applyPreviewLayout(formView, target, state)) {
        updateToggle(toggle, state);
        return;
    }

    if (state.hidden) {
        target?.querySelector(":scope > .fcp-resizer")?.remove();
        applyHiddenLayout(formView, target);
    } else {
        applySideWidth(formView, target, state);
        ensureResizer(formView, target);
    }

    updateToggle(toggle, state);
}

function applyFlexibleChatter(formView) {
    if (!formView) {
        return;
    }

    const sideContainer = findSideContainer(formView);
    const actualChatter = findActualChatter(formView) || sideContainer;
    if (!actualChatter) {
        return;
    }

    const state = getState();
    const isBottom = getUserMode() === "bottom";

    formView.classList.add("fcp-ready");
    formView.classList.toggle("fcp-mode-bottom", isBottom);
    formView.classList.toggle("fcp-mode-responsive", !isBottom);
    formView.classList.toggle("fcp-chatter-hidden", !isBottom && state.hidden);

    if (isBottom) {
        state.hidden = false;
        saveState(state);
        formView.classList.remove("fcp-chatter-hidden", "fcp-preview-open");
        applyBottomLayout(formView, sideContainer, actualChatter);
        return;
    }

    applyResponsiveLayout(formView, sideContainer, actualChatter, state);
}

function initFlexibleChatter(root) {
    const formView = findFormView(root);
    if (formView) {
        applyFlexibleChatter(formView);
    }
    return formView;
}

function getLayoutSignature(formView) {
    if (!formView) {
        return "";
    }
    const renderer = findRenderer(formView);
    const preview = findAttachmentPreview(formView);
    const state = getState();
    const rendererWidth = Math.round(renderer?.getBoundingClientRect().width || 0);
    const previewWidth = Math.round(preview?.getBoundingClientRect().width || 0);
    return [
        getUserMode(),
        state.hidden ? "hidden" : "shown",
        rendererWidth,
        isAttachmentPreviewOpen(formView) ? "preview" : "no-preview",
        previewWidth,
    ].join("|");
}

patch(FormRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        const timers = [];
        let resizeObserver = null;
        let observedFormView = null;
        let observedRenderer = null;
        let observedPreview = null;
        let lastSignature = "";
        let reactiveTimer = null;

        const rootNode = () => this.el instanceof Node ? this.el : document.body;

        const observeCurrentLayout = (formView) => {
            if (!window.ResizeObserver || !formView) {
                return;
            }

            if (!resizeObserver) {
                resizeObserver = new ResizeObserver(() => {
                    if (reactiveTimer) {
                        clearTimeout(reactiveTimer);
                    }
                    reactiveTimer = setTimeout(() => {
                        const currentFormView = findFormView(rootNode());
                        const signature = getLayoutSignature(currentFormView);
                        if (currentFormView && signature !== lastSignature) {
                            applyFlexibleChatter(currentFormView);
                            lastSignature = getLayoutSignature(currentFormView);
                        }
                    }, 40);
                });
            }

            const renderer = findRenderer(formView);
            const preview = findAttachmentPreview(formView);
            if (observedFormView !== formView) {
                if (observedFormView) {
                    resizeObserver.unobserve(observedFormView);
                }
                resizeObserver.observe(formView);
                observedFormView = formView;
            }
            if (renderer && observedRenderer !== renderer) {
                if (observedRenderer) {
                    resizeObserver.unobserve(observedRenderer);
                }
                resizeObserver.observe(renderer);
                observedRenderer = renderer;
            }
            if (preview && observedPreview !== preview) {
                if (observedPreview) {
                    resizeObserver.unobserve(observedPreview);
                }
                resizeObserver.observe(preview);
                observedPreview = preview;
            }
        };

        const scan = () => {
            const formView = initFlexibleChatter(rootNode());
            observeCurrentLayout(formView);
            lastSignature = getLayoutSignature(formView);
        };

        const scheduleScan = () => {
            timers.push(setTimeout(scan, 0));
            timers.push(setTimeout(scan, 120));
            timers.push(setTimeout(scan, 500));
        };

        onMounted(scheduleScan);
        onPatched(scheduleScan);

        onWillUnmount(() => {
            for (const timer of timers) {
                clearTimeout(timer);
            }
            if (reactiveTimer) {
                clearTimeout(reactiveTimer);
            }
            resizeObserver?.disconnect();
        });
    },
});
