/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { FloatTimeField, floatTimeField } from "@web/views/fields/float_time/float_time_field";
import { useInputField } from "@web/views/fields/input_field_hook";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { InvalidNumberError, parseFloat as parseOdooFloat } from "@web/views/fields/parsers";

function parsePositiveInteger(value, originalValue) {
    if (!/^\d+$/.test(value)) {
        throw new InvalidNumberError(`"${originalValue}" is not a correct time`);
    }
    return Number(value);
}

export function parseFloatTimeHMS(value) {
    const rawValue = String(value || "").trim();
    if (!rawValue) {
        return false;
    }

    let sign = 1;
    let normalizedValue = rawValue;
    if (normalizedValue[0] === "-") {
        normalizedValue = normalizedValue.slice(1);
        sign = -1;
    }

    const parts = normalizedValue.split(":");
    if (parts.length === 1) {
        return sign * parseOdooFloat(normalizedValue);
    }
    if (parts.length !== 2 && parts.length !== 3) {
        throw new InvalidNumberError(`"${rawValue}" is not a correct time`);
    }

    const hours = parsePositiveInteger(parts[0], rawValue);
    const minutes = parsePositiveInteger(parts[1], rawValue);
    const seconds = parts.length === 3 ? parsePositiveInteger(parts[2], rawValue) : 0;

    if (minutes > 59 || seconds > 59) {
        throw new InvalidNumberError(`"${rawValue}" is not a correct time`);
    }

    return sign * (hours + minutes / 60 + seconds / 3600);
}

export class FloatTimeHMSField extends FloatTimeField {
    setup() {
        this.inputFloatTimeRef = useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (value) => parseFloatTimeHMS(value),
        });
        useNumpadDecimal();
    }
}

export const floatTimeHMSField = {
    ...floatTimeField,
    component: FloatTimeHMSField,
    displayName: _t("Time (HH:MM:SS)"),
};

registry.category("fields").add("qlk_float_time_hms", floatTimeHMSField);
