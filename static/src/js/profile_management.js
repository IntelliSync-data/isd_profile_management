/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Profile Management Dashboard Widget
 */
class ProfileManagementDashboard extends Component {
    setup() {
        this.state = useState({
            selectedSteps: new Set(),
            totalCost: 0,
            showPaymentInfo: false,
        });
    }

    /**
     * Toggle step selection
     */
    toggleStepSelection(stepId, cost) {
        if (this.state.selectedSteps.has(stepId)) {
            this.state.selectedSteps.delete(stepId);
            this.state.totalCost -= cost;
        } else {
            this.state.selectedSteps.add(stepId);
            this.state.totalCost += cost;
        }
        
        // Update payment info visibility
        this.state.showPaymentInfo = this.state.selectedSteps.size > 0;
    }

    /**
     * Calculate progress percentage
     */
    calculateProgress(completedSteps, totalSteps) {
        if (totalSteps === 0) return 0;
        return Math.round((completedSteps / totalSteps) * 100);
    }

    /**
     * Format currency
     */
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    }

    /**
     * Show payment modal
     */
    showPaymentModal() {
        if (this.state.selectedSteps.size === 0) {
            this.env.services.notification.add(
                "Please select at least one step to proceed with payment.",
                { type: "warning" }
            );
            return;
        }

        // Trigger payment action
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Make Payment',
            res_model: 'profile.payment',
            view_mode: 'form',
            target: 'new',
            context: {
                default_step_ids: Array.from(this.state.selectedSteps),
                default_amount: this.state.totalCost,
            },
        });
    }

    /**
     * Refresh dashboard data
     */
    async refreshDashboard() {
        // Reload the current view
        await this.env.services.action.doAction({
            type: 'ir.actions.client',
            tag: 'reload',
        });
    }
}

ProfileManagementDashboard.template = "isd_profile_management.Dashboard";

// Register the dashboard component
registry.category("actions").add("profile_management_dashboard", ProfileManagementDashboard);

/**
 * Step Selection Widget
 */
class StepSelectionWidget extends Component {
    setup() {
        this.state = useState({
            isSelected: this.props.record.data.is_selected || false,
        });
    }

    /**
     * Toggle step selection
     */
    async toggleSelection() {
        const newValue = !this.state.isSelected;
        
        try {
            await this.props.record.update({
                is_selected: newValue,
            });
            
            this.state.isSelected = newValue;
            
            // Show notification
            const message = newValue ? "Step selected" : "Step deselected";
            this.env.services.notification.add(message, { type: "success" });
            
        } catch (error) {
            this.env.services.notification.add(
                "Error updating step selection",
                { type: "danger" }
            );
        }
    }

    /**
     * Get step status class
     */
    getStatusClass() {
        const state = this.props.record.data.state;
        const isSelected = this.state.isSelected;
        
        let classes = ['profile_step_card'];
        
        if (isSelected) classes.push('selected');
        if (state) classes.push(state);
        
        return classes.join(' ');
    }
}

StepSelectionWidget.template = "isd_profile_management.StepSelection";
StepSelectionWidget.props = ["record"];

// Register the step selection widget
registry.category("view_widgets").add("step_selection", StepSelectionWidget);

/**
 * Progress Bar Widget
 */
class ProgressBarWidget extends Component {
    get progressWidth() {
        const percentage = this.props.record.data[this.props.field] || 0;
        return Math.min(Math.max(percentage, 0), 100);
    }

    get progressColor() {
        const percentage = this.progressWidth;
        if (percentage < 30) return '#dc3545'; // Red
        if (percentage < 70) return '#ffc107'; // Yellow
        return '#28a745'; // Green
    }
}

ProgressBarWidget.template = "isd_profile_management.ProgressBar";
ProgressBarWidget.props = ["record", "field"];

// Register the progress bar widget
registry.category("view_widgets").add("profile_progress", ProgressBarWidget);

/**
 * Payment Status Widget
 */
class PaymentStatusWidget extends Component {
    get statusClass() {
        const status = this.props.record.data[this.props.field];
        return `payment_status_badge ${status}`;
    }

    get statusText() {
        const status = this.props.record.data[this.props.field];
        return status ? status.replace('_', ' ').toUpperCase() : '';
    }
}

PaymentStatusWidget.template = "isd_profile_management.PaymentStatus";
PaymentStatusWidget.props = ["record", "field"];

// Register the payment status widget
registry.category("view_widgets").add("payment_status", PaymentStatusWidget);

/**
 * Utility functions for profile management
 */
export const ProfileUtils = {
    /**
     * Calculate total cost for selected steps
     */
    calculateTotalCost(steps) {
        return steps
            .filter(step => step.is_selected)
            .reduce((total, step) => total + (step.cost || 0), 0);
    },

    /**
     * Get step status color
     */
    getStepStatusColor(state) {
        const colors = {
            'not_started': '#6c757d',
            'in_progress': '#ffc107',
            'completed': '#28a745',
            'cancelled': '#dc3545',
            'pending_approval': '#007bff',
        };
        return colors[state] || '#6c757d';
    },

    /**
     * Format step status for display
     */
    formatStepStatus(state) {
        const statuses = {
            'not_started': 'Not Started',
            'in_progress': 'In Progress',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
            'pending_approval': 'Pending Approval',
        };
        return statuses[state] || state;
    },

    /**
     * Check if all prerequisites are met
     */
    arePrerequisitesMet(step, allSteps) {
        if (!step.prerequisite_step_ids || step.prerequisite_step_ids.length === 0) {
            return true;
        }

        return step.prerequisite_step_ids.every(prereqId => {
            const prereqStep = allSteps.find(s => s.id === prereqId);
            return prereqStep && prereqStep.state === 'completed';
        });
    },
};

console.log('Profile Management JavaScript loaded successfully');