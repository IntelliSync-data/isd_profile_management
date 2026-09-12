/** @odoo-module **/

import { registry } from "@web/core/registry";

function renderTemplate(template, data) {
    return template.replace(/\{\{(\w+)\}\}/g, function (match, key) {
        return data.hasOwnProperty(key) ? data[key] : match;
    });
}

function generateBarcodeSVG(value) {
    if (!value) return '';
    // Code 128 simplified — render as SVG bars
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
    // Use a simple QR placeholder that the browser can render
    // For production, this uses a canvas-based approach
    var size = 150;
    var canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    var ctx = canvas.getContext('2d');

    // Simple QR-like pattern generation using XOR pattern
    var moduleSize = 5;
    var modules = Math.floor(size / moduleSize);
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = 'black';

    // Generate a deterministic pattern from the value
    var hash = 0;
    for (var i = 0; i < value.length; i++) {
        hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0;
    }

    // Finder patterns (3 corners)
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

    // Data pattern
    var seed = Math.abs(hash);
    for (var row = 0; row < modules; row++) {
        for (var col = 0; col < modules; col++) {
            // Skip finder pattern areas
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

async function printLabel(env, action) {
    var params = action.params || {};
    var width = params.width || 100;
    var height = params.height || 60;
    var codeType = params.code_type || 'none';
    var trackingNumber = params.tracking_number || '';
    var template = params.template || '';
    var data = params.data || {};

    // Generate code HTML
    var codeHtml = '';
    if (codeType === 'barcode' && trackingNumber) {
        codeHtml = generateBarcodeSVG(trackingNumber);
    } else if (codeType === 'qrcode' && trackingNumber) {
        codeHtml = generateQRCodeSVG(trackingNumber);
    }

    // Add code to data for template replacement
    data.code = codeHtml;
    data.barcode = codeType === 'barcode' ? codeHtml : '';
    data.qrcode = codeType === 'qrcode' ? codeHtml : '';

    // Render template
    var renderedHtml = renderTemplate(template, data);

    // Open print window
    var printWindow = window.open('', '_blank', 'width=600,height=400');
    if (!printWindow) {
        env.services.notification.add('Pop-up blocked. Please allow pop-ups for this site.', { type: 'warning' });
        return;
    }

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
}

registry.category("actions").add("isd_print_label", printLabel);
