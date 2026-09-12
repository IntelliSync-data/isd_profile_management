/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

function renderTemplate(template, data) {
    return template.replace(/\{\{(\w+)\}\}/g, function (match, key) {
        return data.hasOwnProperty(key) ? data[key] : match;
    });
}

function generateBarcodeSVG(value) {
    if (!value) return '';
    var encoded = [];
    for (var i = 0; i < value.length; i++) {
        var code = value.charCodeAt(i);
        var binary = code.toString(2).padStart(8, '0');
        encoded.push(binary);
    }
    var pattern = encoded.join('0');
    var barWidth = 2;
    var height = 60;
    var totalWidth = pattern.length * barWidth;
    var bars = '';
    for (var j = 0; j < pattern.length; j++) {
        if (pattern[j] === '1') {
            bars += '<rect x="' + (j * barWidth) + '" y="0" width="' + barWidth + '" height="' + height + '" fill="black"/>';
        }
    }
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + totalWidth + '" height="' + (height + 20) + '" viewBox="0 0 ' + totalWidth + ' ' + (height + 20) + '">' +
        bars +
        '<text x="' + (totalWidth / 2) + '" y="' + (height + 16) + '" text-anchor="middle" font-family="monospace" font-size="14">' + value + '</text>' +
        '</svg>';
}

function generateQRCodeSVG(value) {
    if (!value) return '';
    var size = 150;
    var canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    var ctx = canvas.getContext('2d');

    var moduleSize = 5;
    var modules = Math.floor(size / moduleSize);
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = 'black';

    var hash = 0;
    for (var i = 0; i < value.length; i++) {
        hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0;
    }

    function drawFinder(x, y) {
        for (var r = 0; r < 7; r++) {
            for (var c = 0; c < 7; c++) {
                var isBorder = r === 0 || r === 6 || c === 0 || c === 6;
                var isInner = r >= 2 && r <= 4 && c >= 2 && c <= 4;
                if (isBorder || isInner) {
                    ctx.fillRect((x + c) * moduleSize, (y + r) * moduleSize, moduleSize, moduleSize);
                }
            }
        }
    }
    drawFinder(0, 0);
    drawFinder(modules - 7, 0);
    drawFinder(0, modules - 7);

    var seed = Math.abs(hash);
    for (var row = 0; row < modules; row++) {
        for (var col = 0; col < modules; col++) {
            if ((row < 8 && col < 8) || (row < 8 && col >= modules - 8) || (row >= modules - 8 && col < 8)) continue;
            seed = (seed * 1103515245 + 12345) & 0x7fffffff;
            if (seed % 3 === 0) {
                ctx.fillRect(col * moduleSize, row * moduleSize, moduleSize, moduleSize);
            }
        }
    }

    var dataUrl = canvas.toDataURL('image/png');
    return '<div style="text-align:center"><img src="' + dataUrl + '" width="' + size + '" height="' + size + '"/>' +
        '<div style="font-family:monospace;font-size:12px;margin-top:4px">' + value + '</div></div>';
}

function openPrintWindow(params) {
    var width = params.width || 100;
    var height = params.height || 60;
    var codeType = params.code_type || 'none';
    var trackingNumber = params.tracking_number || '';
    var template = params.template || '';
    var data = params.data || {};

    var codeHtml = '';
    if (codeType === 'barcode' && trackingNumber) {
        codeHtml = generateBarcodeSVG(trackingNumber);
    } else if (codeType === 'qrcode' && trackingNumber) {
        codeHtml = generateQRCodeSVG(trackingNumber);
    }

    data.code = codeHtml;
    data.barcode = codeType === 'barcode' ? codeHtml : '';
    data.qrcode = codeType === 'qrcode' ? codeHtml : '';

    var renderedHtml = renderTemplate(template, data);

    var printWindow = window.open('', '_blank', 'width=600,height=400');
    if (!printWindow) return false;

    var pageHtml = '<!DOCTYPE html><html><head><meta charset="utf-8">' +
        '<title>Print Label</title>' +
        '<style>' +
        '@page { size: ' + width + 'mm ' + height + 'mm; margin: 0; }' +
        '* { margin: 0; padding: 0; box-sizing: border-box; }' +
        'body { width: ' + width + 'mm; height: ' + height + 'mm; font-family: Arial, sans-serif; }' +
        'img, svg { max-width: 100%; }' +
        '</style></head><body>' +
        renderedHtml +
        '<script>window.onload = function() { window.print(); window.onafterprint = function() { window.close(); }; };<\/script>' +
        '</body></html>';

    printWindow.document.write(pageHtml);
    printWindow.document.close();
    return true;
}

function showPrintDialog(params) {
    var stepId = params.step_id;
    var stepName = params.step_name || '';
    var trackingNumber = params.tracking_number || '';

    var backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop fade show';
    backdrop.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1050;';

    var modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:1055;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML =
        '<div style="background:white;border-radius:8px;width:500px;max-width:90%;box-shadow:0 5px 30px rgba(0,0,0,0.3);">' +
            '<div style="padding:16px 20px;border-bottom:1px solid #dee2e6;display:flex;justify-content:space-between;align-items:center;">' +
                '<h5 style="margin:0;font-size:1.1rem;">Print Label</h5>' +
                '<button class="isd-print-close" style="background:none;border:none;font-size:1.5rem;cursor:pointer;padding:0;line-height:1;">&times;</button>' +
            '</div>' +
            '<div style="padding:20px;">' +
                '<div style="margin-bottom:16px;">' +
                    '<label style="display:block;font-weight:600;margin-bottom:4px;">Step</label>' +
                    '<div style="padding:6px 12px;background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;">' + (stepName ? stepName.replace(/</g,'&lt;') : '') + '</div>' +
                '</div>' +
                '<div style="margin-bottom:8px;">' +
                    '<label for="isd_tracking_input" style="display:block;font-weight:600;margin-bottom:4px;">Tracking Number</label>' +
                    '<input type="text" id="isd_tracking_input" class="form-control" style="width:100%;padding:6px 12px;border:1px solid #ced4da;border-radius:4px;" ' +
                    'value="' + (trackingNumber ? trackingNumber.replace(/"/g,'&quot;') : '') + '" placeholder="Enter tracking/shipping number..."/>' +
                '</div>' +
            '</div>' +
            '<div style="padding:12px 20px;border-top:1px solid #dee2e6;display:flex;justify-content:flex-end;gap:8px;">' +
                '<button class="isd-print-cancel btn btn-secondary" style="padding:6px 20px;">Cancel</button>' +
                '<button class="isd-print-submit btn btn-primary" style="padding:6px 20px;">Print</button>' +
            '</div>' +
        '</div>';

    document.body.appendChild(backdrop);
    document.body.appendChild(modal);

    var input = modal.querySelector('#isd_tracking_input');
    if (input) input.focus();

    function closeDialog() {
        try { document.body.removeChild(modal); } catch (e) {}
        try { document.body.removeChild(backdrop); } catch (e) {}
    }

    modal.querySelector('.isd-print-close').addEventListener('click', closeDialog);
    modal.querySelector('.isd-print-cancel').addEventListener('click', closeDialog);
    backdrop.addEventListener('click', closeDialog);

    modal.querySelector('.isd-print-submit').addEventListener('click', async function () {
        var tn = input.value.trim();
        if (!tn) {
            input.style.borderColor = '#dc3545';
            input.focus();
            return;
        }

        var btn = modal.querySelector('.isd-print-submit');
        btn.disabled = true;
        btn.textContent = 'Loading...';

        try {
            var result = await rpc("/web/dataset/call_kw/user.step/action_print_label", {
                model: "user.step",
                method: "action_print_label",
                args: [[stepId], tn],
                kwargs: {},
            });

            if (result && result.template) {
                var ok = openPrintWindow(result);
                if (!ok) {
                    alert("Pop-up blocked. Please allow pop-ups for this site.");
                    btn.disabled = false;
                    btn.textContent = 'Print';
                    return;
                }
                closeDialog();
            } else {
                alert("No print template configured for this step.");
                btn.disabled = false;
                btn.textContent = 'Print';
            }
        } catch (e) {
            alert("Error: " + (e.message || e.data?.message || String(e)));
            btn.disabled = false;
            btn.textContent = 'Print';
        }
    });

    if (input) {
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                modal.querySelector('.isd-print-submit').click();
            }
        });
    }
}

async function printLabelAction(env, action) {
    var params = action.params || {};

    if (params.template) {
        openPrintWindow(params);
        return;
    }

    showPrintDialog(params);
}

registry.category("actions").add("isd_print_label", printLabelAction);
