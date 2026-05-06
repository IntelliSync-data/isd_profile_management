/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Many2ManyCheckboxesField } from "@web/views/fields/many2many_checkboxes/many2many_checkboxes_field";

export class StepSelectionWidget extends Many2ManyCheckboxesField {
    setup() {
        super.setup();
        // Force refresh after component is mounted
        setTimeout(() => {
            this.render();
        }, 50);
    }

    async willUpdateProps(nextProps) {
        await super.willUpdateProps(nextProps);
        // Force re-render when props change
        this.render();
    }
}

StepSelectionWidget.template = "web.Many2ManyCheckboxesField";

registry.category("fields").add("step_selection_checkboxes", StepSelectionWidget);