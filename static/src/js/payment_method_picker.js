/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUpdateProps, xml } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

const PROVIDER_ICONS = {
    sepay: "fa-qrcode",
    paypal: "fa-paypal",
    vtcpay: "fa-credit-card",
};

class PaymentMethodPickerField extends Component {
    static template = xml`
        <div class="pm_method_cards_wrapper">
            <t t-if="state.methods.length === 0">
                <div class="pm_method_cards_empty">No payment methods available.</div>
            </t>
            <t t-else="">
                <div class="pm_method_cards">
                    <t t-foreach="state.methods" t-as="method" t-key="method.id">
                        <div
                            t-attf-class="pm_method_card{{ isSelected(method.id) ? ' selected' : '' }}"
                            t-on-click="() => this.selectMethod(method)"
                        >
                            <t t-if="method.image">
                                <img
                                    t-attf-src="/web/image/isd_payment.method/{{ method.id }}/image"
                                    class="pm_card_image"
                                    t-att-alt="method.name"
                                />
                            </t>
                            <t t-else="">
                                <i t-attf-class="fa {{ providerIcon(method.payment_provider) }} pm_card_icon"/>
                            </t>
                            <span class="pm_card_name" t-esc="method.name"/>
                        </div>
                    </t>
                </div>
            </t>
        </div>
    `;

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ methods: [] });

        onWillStart(async () => {
            await this._loadMethods(this.props);
        });

        onWillUpdateProps(async (nextProps) => {
            await this._loadMethods(nextProps);
        });
    }

    async _loadMethods(props) {
        const availableMethods = props.record.data.available_method_ids;
        // available_method_ids is a Many2many — its records are in .records or it may be a list of IDs
        let ids = [];
        if (availableMethods) {
            if (Array.isArray(availableMethods)) {
                ids = availableMethods.filter((v) => typeof v === "number");
            } else if (availableMethods.records && availableMethods.records.length) {
                ids = availableMethods.records.map((r) => r.resId ?? r.data?.id ?? r.id).filter(Boolean);
            } else if (availableMethods.currentIds && availableMethods.currentIds.length) {
                ids = availableMethods.currentIds;
            }
        }

        if (ids.length === 0) {
            this.state.methods = [];
            return;
        }

        const results = await this.orm.read(
            "isd_payment.method",
            ids,
            ["name", "image", "payment_provider"]
        );
        this.state.methods = results;
    }

    isSelected(methodId) {
        const current = this.props.record.data.payment_method_id;
        if (!current) return false;
        // Many2one data is [id, display_name] or an object with id
        if (Array.isArray(current)) return current[0] === methodId;
        if (typeof current === "object") return current.id === methodId;
        return current === methodId;
    }

    selectMethod(method) {
        this.props.record.update({ payment_method_id: [method.id, method.name] });
    }

    providerIcon(provider) {
        return PROVIDER_ICONS[provider] || "fa-money";
    }
}

registry.category("fields").add("payment_method_picker", PaymentMethodPickerField);
