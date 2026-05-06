// Lightweight QR poller without depending on Odoo JS modules
// This avoids RequireJS dependency issues and uses fetch directly.
(function () {
    'use strict';

    console.info('isd_profile_management: qr_poll loaded');

    function startPollingForModal(modalEl, transactionId) {
        if (!modalEl || !transactionId) return;
        if (modalEl.__qrPollStarted) return; // already started
        modalEl.__qrPollStarted = true;

        console.info('Starting QR poll for transaction:', transactionId);

        var intervalId = setInterval(function () {
            fetch('/isd_profile_management/payment/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({transaction_id: transactionId}),
            }).then(function (r) {
                return r.json();
            }).then(function (resp) {
                if (resp && resp.success && (resp.status === 'confirmed' || resp.status === 'paid')) {
                    console.info('Payment confirmed for', transactionId, resp);
                    try { clearInterval(intervalId); } catch (e) {}
                    // Reload the page to reflect updated state (this will close modal)
                    window.location.reload();
                }
            }).catch(function (err) {
                console.debug('QR poll fetch error', err);
            });
        }, 10000);

        // store interval so we can clear if modal removed
        modalEl.__qrPollInterval = intervalId;

        // Attach handlers so that clicking Close/X or bootstrap hidden event
        // will stop the polling immediately instead of waiting for node removal.
        // Use event references so we can remove them later.
        try {
            // Click handler (capturing) - stops polling when Close/X inside modal clicked
            modalEl.__qrPollClickHandler = function (ev) {
                try {
                    var t = ev.target;
                    if (!t) return;
                    // Look for common modal-close elements (Bootstrap/Odoo patterns)
                    var closeBtn = null;
                    if (t.closest) {
                        closeBtn = t.closest('[data-bs-dismiss], [data-dismiss], .btn-close, .close, [aria-label="Close"]');
                    }
                    // If the clicked close is within the modal root (or the modal root contains the clicked element), stop polling
                    if (closeBtn) {
                        var inside = (modalEl && modalEl.contains) ? modalEl.contains(closeBtn) : false;
                        if (inside || modalEl === document.body) {
                            console.info('QR poll: detected close click inside modal, stopping poll');
                            stopPollingForModal(modalEl);
                            return;
                        }
                    }
                    // Also, if the click happened on an element inside the modal that likely triggers a close (buttons in footer), handle it
                    if (modalEl && modalEl.contains && modalEl.contains(t)) {
                        if (t.closest && (t.closest('button') || t.tagName === 'BUTTON' || t.tagName === 'A')) {
                            console.info('QR poll: click inside modal element, stopping poll');
                            stopPollingForModal(modalEl);
                        }
                    }
                } catch (e) { /* ignore */ }
            };
            // Listen on document with capturing so clicks inside Shadow/portal still reach
            document.addEventListener('click', modalEl.__qrPollClickHandler, true);

            // Also listen for Escape key to close modal
            modalEl.__qrPollKeyHandler = function (ev) {
                try {
                    if (ev.key === 'Escape' || ev.key === 'Esc') {
                        if (!modalEl) return;
                        var active = document.activeElement;
                        if (modalEl.contains(active) || modalEl === document.body) {
                            console.info('QR poll: Escape pressed, stopping poll');
                            stopPollingForModal(modalEl);
                        }
                    }
                } catch (e) { }
            };
            document.addEventListener('keydown', modalEl.__qrPollKeyHandler, true);

            // Bootstrap modal hidden event handler (if Bootstrap used)
            modalEl.__qrPollHiddenHandler = function () {
                stopPollingForModal(modalEl);
            };
            if (modalEl.addEventListener) {
                modalEl.addEventListener('hidden.bs.modal', modalEl.__qrPollHiddenHandler);
            }
        } catch (e) { console.debug('Error attaching modal close handlers', e); }
    }

    function stopPollingForModal(modalEl) {
        if (!modalEl) return;
        try {
            if (modalEl.__qrPollInterval) {
                clearInterval(modalEl.__qrPollInterval);
                modalEl.__qrPollInterval = null;
            }
            // Remove any attached handlers
            try {
                if (modalEl.__qrPollClickHandler) {
                    document.removeEventListener('click', modalEl.__qrPollClickHandler, true);
                    modalEl.__qrPollClickHandler = null;
                }
            } catch (e) { /* ignore */ }
            try {
                if (modalEl.__qrPollHiddenHandler && modalEl.removeEventListener) {
                    modalEl.removeEventListener('hidden.bs.modal', modalEl.__qrPollHiddenHandler);
                    modalEl.__qrPollHiddenHandler = null;
                }
            } catch (e) { /* ignore */ }
        } catch (e) { /* ignore */ }
        modalEl.__qrPollStarted = false;
    }

    function extractTransactionIdFromElement(el) {
        if (!el) return null;
        // Prefer .value for inputs
        try {
            if (el.value) return el.value;
        } catch (e) {}
        // If it's a field widget (div with span), try to read span text
        var span = el.querySelector && el.querySelector('span');
        if (span && span.textContent) return span.textContent.trim();
        // Fallback to textContent
        if (el.textContent) return el.textContent.trim();
        return null;
    }

    function inspectNode(node) {
        try {
            if (!node.querySelector) return;
            console.info('Inspecting node for transaction_id:', node);
            // Look for any element with name="transaction_id" (input or widget)
            var el = node.querySelector('[name="transaction_id"]');
            if (el) {
                var tx = extractTransactionIdFromElement(el);
                if (tx) {
                    console.info('Found transaction_id in modal (any element):', tx);
                    var modalRoot = (el.closest && (el.closest('.modal') || el.closest('.o_dialog') || el.closest('.o_modal_full'))) || node;
                    startPollingForModal(modalRoot, tx);
                    return;
                }
            }
            // Also try to find readonly widget by class that may contain the id in a span
            var widget = node.querySelector('.o_field_widget[name="transaction_id"]');
            if (widget) {
                var tx2 = extractTransactionIdFromElement(widget);
                if (tx2) {
                    console.info('Found transaction_id in field widget:', tx2);
                    var modalRoot2 = (widget.closest && (widget.closest('.modal') || widget.closest('.o_dialog') || widget.closest('.o_modal_full'))) || node;
                    startPollingForModal(modalRoot2, tx2);
                }
            }
        } catch (e) { console.debug(e); }
    }

    // Observe added nodes to detect modal popups
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
            m.addedNodes && m.addedNodes.forEach(function (n) {
                inspectNode(n);
            });
            m.removedNodes && m.removedNodes.forEach(function (n) {
                try {
                    if (n && n.__qrPollInterval) {
                        stopPollingForModal(n);
                    }
                } catch (e) { }
            });
        });
    });

    // Start observing body
    if (document && document.body) {
        observer.observe(document.body, {childList: true, subtree: true});
        // Also inspect existing nodes (in case modal already present)
        inspectNode(document.body);
    }
    // Listen for Bootstrap modal shown events so we can detect when an existing
    // modal is shown again (Bootstrap toggles visibility instead of re-adding nodes).
    try {
        document.addEventListener('shown.bs.modal', function (e) {
            try {
                if (e && e.target) {
                    inspectNode(e.target);
                }
            } catch (err) { /* ignore */ }
        });
    } catch (e) { /* ignore */ }

    // Also listen for clicks on modal opener elements (data-bs-toggle/data-toggle)
    // and trigger a short delayed scan to catch modals rendered via JS.
    try {
        document.addEventListener('click', function (ev) {
            try {
                var opener = ev.target && ev.target.closest && ev.target.closest('[data-bs-toggle="modal"],[data-toggle="modal"],[data-bs-target],[data-target]');
                if (opener) {
                    setTimeout(function () {
                        try {
                            var sel = opener.getAttribute('data-bs-target') || opener.getAttribute('data-target');
                            if (sel) {
                                try {
                                    var modal = document.querySelector(sel);
                                    if (modal) { inspectNode(modal); return; }
                                } catch (e) { /* ignore */ }
                            }
                            inspectNode(document.body);
                        } catch (e) { /* ignore */ }
                    }, 50);
                }
            } catch (e) { /* ignore */ }
        }, true);
    } catch (e) { /* ignore */ }
    // Persistent scanner: some modals are shown/hidden without DOM additions
    // Keep scanning for transaction_id elements and start polling when found.
    var fallbackScannerInterval = setInterval(function () {
        try {
            var els = document.querySelectorAll && document.querySelectorAll('[name="transaction_id"]');
            if (els && els.length) {
                els.forEach(function (el) {
                    try {
                        var root = (el.closest && (el.closest('.modal') || el.closest('.o_dialog') || el.closest('.o_modal_full') || el.closest('.o_form_renderer'))) || document.body;
                        // If there's no active poll for this root, inspect it and potentially start polling
                        if (!root || !root.__qrPollStarted) {
                            console.info('QR poll scanner: found transaction element, inspecting root', root);
                            inspectNode(root);
                        }
                    } catch (e) { console.debug(e); }
                });
            }
        } catch (e) { /* ignore */ }
    }, 1000);
})();

