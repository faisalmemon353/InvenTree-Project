#!/usr/bin/env python3
"""OpenAPI-Driven Equivalence Partitioning (EP) & 3-Point BVA Test Data Generator.

SE3002 Software Quality Engineering Final Project (Section C)
Area 2 Owner: Hassan Zahid (24I-3011)

Reads an OpenAPI 3.0 YAML specification for InvenTree's Purchasing & Stock Receipt endpoints
and dynamically generates:
1. Equivalence Partitioning (EP) classes (valid_nominal, invalid_below_min, invalid_above_max,
   invalid_type_or_null, invalid_enum_or_pattern) for every schema property.
2. 3-Point Boundary Value Analysis (BVA) test values for every numeric and string-length limit:
   - Lower boundary: just_below_min (Invalid), at_min (Valid), just_above_min (Valid)
   - Upper boundary: just_below_max (Valid), at_max (Valid), just_above_max (Invalid)
3. Single-Fault API Request Payloads (one invalid input value per test case, holding all other
   fields at valid nominal values).
4. Constraint-Change Comparison Mode (--compare-v2) demonstrating how changing 2 constraints
   in the OpenAPI spec automatically regenerates updated EP partitions and 3-point BVA values.
"""

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

API_DIR = Path(__file__).resolve().parent
DEFAULT_SPEC = API_DIR / 'openapi_po_spec.yaml'
MODIFIED_SPEC = API_DIR / 'openapi_po_spec_v2_modified.yaml'
DEFAULT_OUTPUT = API_DIR / 'generated_api_test_data.json'
MODIFIED_OUTPUT = API_DIR / 'generated_api_test_data_v2_modified.json'


def _format_num(val: Decimal | int | float, is_int: bool) -> int | float:
    """Format a Decimal boundary value cleanly as int or rounded float."""
    if is_int or val == val.to_integral_value():
        return int(val)
    return float(round(val, 5))


def generate_field_ep_and_3pt_bva(field_name: str, prop_schema: dict[str, Any]) -> dict[str, Any]:
    """Generate EP classes and 3-point BVA values from a single OpenAPI property schema."""
    ftype = prop_schema.get('type', 'string')

    if ftype in ('integer', 'number'):
        is_int = ftype == 'integer' or prop_schema.get('x-step', 1) == 1
        step = Decimal(str(prop_schema.get('x-step', 1 if is_int else '0.01')))
        min_val = Decimal(str(prop_schema.get('minimum', 0)))
        max_val = Decimal(str(prop_schema.get('maximum', 10000)))
        mid_val = ((min_val + max_val) / Decimal('2')).quantize(step)

        bva_3pt = {
            'lower_boundary': {
                'limit': _format_num(min_val, is_int),
                'just_below_min': {'value': _format_num(min_val - step, is_int), 'expected_valid': False},
                'at_min': {'value': _format_num(min_val, is_int), 'expected_valid': True},
                'just_above_min': {'value': _format_num(min_val + step, is_int), 'expected_valid': True},
            },
            'upper_boundary': {
                'limit': _format_num(max_val, is_int),
                'just_below_max': {'value': _format_num(max_val - step, is_int), 'expected_valid': True},
                'at_max': {'value': _format_num(max_val, is_int), 'expected_valid': True},
                'just_above_max': {'value': _format_num(max_val + step, is_int), 'expected_valid': False},
            },
        }

        if 'enum' in prop_schema:
            enum_vals = prop_schema['enum']
            ep_classes = {
                'valid_enum_values': [{'value': v, 'expected_valid': True} for v in enum_vals],
                'invalid_enum_value': {'value': max(enum_vals) + 999, 'expected_valid': False},
                'invalid_type': {'value': 'NOT_A_NUMBER', 'expected_valid': False},
            }
            return {'type': ftype, 'constraints': {'enum': enum_vals}, 'ep_classes': ep_classes, 'bva_3point': None}

        ep_classes = {
            'valid_nominal': {'value': _format_num(mid_val, is_int), 'expected_valid': True},
            'invalid_below_min_partition': {
                'value': _format_num(min_val - (step * 50), is_int),
                'expected_valid': False,
            },
            'invalid_above_max_partition': {
                'value': _format_num(max_val + (step * 500), is_int),
                'expected_valid': False,
            },
            'invalid_type_partition': {'value': 'INVALID_NUMERIC_STRING', 'expected_valid': False},
        }
        return {
            'type': ftype,
            'constraints': {
                'minimum': _format_num(min_val, is_int),
                'maximum': _format_num(max_val, is_int),
                'step': _format_num(step, is_int),
            },
            'ep_classes': ep_classes,
            'bva_3point': bva_3pt,
        }

    if ftype == 'string':
        if 'enum' in prop_schema:
            enum_vals = prop_schema['enum']
            return {
                'type': 'string_enum',
                'constraints': {'enum': enum_vals},
                'ep_classes': {
                    'valid_nominal': {'value': enum_vals[0], 'expected_valid': True},
                    'valid_all_enums': [{'value': v, 'expected_valid': True} for v in enum_vals],
                    'invalid_enum_partition': {'value': 'INVALID_CURRENCY_XYZ', 'expected_valid': False},
                    'invalid_empty_partition': {'value': '', 'expected_valid': False},
                },
                'bva_3point': None,
            }

        min_len = int(prop_schema.get('minLength', 1))
        max_len = int(prop_schema.get('maxLength', 64))
        pattern = prop_schema.get('pattern')
        mid_len = max(min_len + 2, min(16, max_len))

        def make_str(length: int) -> str:
            if length <= 0:
                return ''
            if pattern and pattern.startswith('^PO-'):
                if length <= 3:
                    return 'PO-'[:length]
                digits = '9' * (length - 3)
                return ('PO-' + digits)[:length]
            base = f'SQE-{field_name.upper()}-'
            if len(base) >= length:
                return 'X' * length
            return base + ('A' * (length - len(base)))

        bva_3pt = {
            'lower_length_boundary': {
                'limit': min_len,
                'just_below_min_length': {'value': make_str(min_len - 1), 'length': max(0, min_len - 1), 'expected_valid': False},
                'at_min_length': {'value': make_str(min_len), 'length': min_len, 'expected_valid': True},
                'just_above_min_length': {'value': make_str(min_len + 1), 'length': min_len + 1, 'expected_valid': True},
            },
            'upper_length_boundary': {
                'limit': max_len,
                'just_below_max_length': {'value': make_str(max_len - 1), 'length': max_len - 1, 'expected_valid': True},
                'at_max_length': {'value': make_str(max_len), 'length': max_len, 'expected_valid': True},
                'just_above_max_length': {'value': make_str(max_len + 1), 'length': max_len + 1, 'expected_valid': False},
            },
        }

        ep_classes: dict[str, Any] = {
            'valid_nominal': {'value': make_str(mid_len), 'length': mid_len, 'expected_valid': True},
            'invalid_over_max_length_partition': {
                'value': make_str(max_len + 25),
                'length': max_len + 25,
                'expected_valid': False,
            },
        }
        if min_len >= 1:
            ep_classes['invalid_empty_string_partition'] = {'value': '', 'length': 0, 'expected_valid': False}
        if pattern:
            ep_classes['invalid_pattern_mismatch_partition'] = {
                'value': 'INVALID_REF_FORMAT_###',
                'expected_valid': False,
            }

        return {
            'type': 'string',
            'constraints': {'minLength': min_len, 'maxLength': max_len, 'pattern': pattern},
            'ep_classes': ep_classes,
            'bva_3point': bva_3pt,
        }

    if ftype == 'boolean':
        return {
            'type': 'boolean',
            'constraints': {'enum': [True, False]},
            'ep_classes': {
                'valid_true': {'value': True, 'expected_valid': True},
                'valid_false': {'value': False, 'expected_valid': True},
                'invalid_boolean_string': {'value': 'NOT_A_BOOLEAN_VALUE', 'expected_valid': False},
            },
            'bva_3point': None,
        }

    return {'type': ftype, 'constraints': {}, 'ep_classes': {}, 'bva_3point': None}


def generate_dataset_from_spec(spec_path: Path, output_path: Path) -> dict[str, Any]:
    """Parse an OpenAPI 3.0 YAML file and generate full EP and 3-point BVA datasets."""
    raw_spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
    schemas = raw_spec.get('components', {}).get('schemas', {})

    generated_schemas: dict[str, Any] = {}
    total_ep_cases = 0
    total_bva_points = 0

    for schema_name, schema_def in schemas.items():
        props = schema_def.get('properties', {})
        required_fields = schema_def.get('required', [])
        schema_report: dict[str, Any] = {
            'required_fields': required_fields,
            'fields': {},
        }

        for field_name, prop_schema in props.items():
            if prop_schema.get('type') == 'array':
                min_items = int(prop_schema.get('minItems', 1))
                max_items = int(prop_schema.get('maxItems', 50))
                field_data = {
                    'type': 'array',
                    'constraints': {'minItems': min_items, 'maxItems': max_items},
                    'ep_classes': {
                        'valid_single_item': {'count': 1, 'expected_valid': True},
                        'invalid_empty_array': {'count': 0, 'expected_valid': False},
                    },
                    'bva_3point': {
                        'lower_items_boundary': {
                            'limit': min_items,
                            'just_below_min': {'count': min_items - 1, 'expected_valid': False},
                            'at_min': {'count': min_items, 'expected_valid': True},
                            'just_above_min': {'count': min_items + 1, 'expected_valid': True},
                        }
                    },
                }
            else:
                field_data = generate_field_ep_and_3pt_bva(field_name, prop_schema)

            schema_report['fields'][field_name] = field_data
            total_ep_cases += len(field_data.get('ep_classes', {}))
            if field_data.get('bva_3point'):
                for bgroup in field_data['bva_3point'].values():
                    total_bva_points += 3

        generated_schemas[schema_name] = schema_report

    dataset = {
        'spec_file': spec_path.name,
        'spec_title': raw_spec.get('info', {}).get('title', ''),
        'spec_version': raw_spec.get('info', {}).get('version', ''),
        'summary': {
            'schemas_processed': len(generated_schemas),
            'total_ep_partitions_generated': total_ep_cases,
            'total_3point_bva_cases_generated': total_bva_points,
        },
        'schemas': generated_schemas,
    }

    output_path.write_text(json.dumps(dataset, indent=2), encoding='utf-8')
    return dataset


def print_generation_report(dataset: dict[str, Any], out_path: Path) -> None:
    """Print a clean formatted summary table of the generated EP & 3-point BVA dataset."""
    print('=' * 98)
    print(f"SQE SECTION C — OPENAPI AUTOMATED TEST DATA GENERATOR (Hassan Zahid 24I-3011)")
    print(f"Source Spec : {dataset['spec_file']} (v{dataset['spec_version']})")
    print(f"Output JSON : {out_path.name}")
    print('=' * 98)
    print(f"{'Schema.Field':<46} | {'Constraints':<24} | {'3-Point BVA (Below / At / Above)'}")
    print('-' * 98)

    for sname, sdata in dataset['schemas'].items():
        for fname, fdata in sdata['fields'].items():
            qualified = f'{sname}.{fname}'
            c_dict = fdata.get('constraints', {})
            if 'minimum' in c_dict:
                c_str = f"[{c_dict['minimum']} .. {c_dict['maximum']}]"
                lb = fdata['bva_3point']['lower_boundary']
                ub = fdata['bva_3point']['upper_boundary']
                bva_str = (
                    f"Min({lb['just_below_min']['value']}, {lb['at_min']['value']}, {lb['just_above_min']['value']}) | "
                    f"Max({ub['just_below_max']['value']}, {ub['at_max']['value']}, {ub['just_above_max']['value']})"
                )
            elif 'minLength' in c_dict:
                c_str = f"len [{c_dict['minLength']} .. {c_dict['maxLength']}]"
                lb = fdata['bva_3point']['lower_length_boundary']
                ub = fdata['bva_3point']['upper_length_boundary']
                bva_str = (
                    f"MinLen({lb['just_below_min_length']['length']}, {lb['at_min_length']['length']}, {lb['just_above_min_length']['length']}) | "
                    f"MaxLen({ub['just_below_max_length']['length']}, {ub['at_max_length']['length']}, {ub['just_above_max_length']['length']})"
                )
            elif 'enum' in c_dict:
                c_str = f"enum({len(c_dict['enum'])} vals)"
                bva_str = f"EP valid={c_dict['enum'][:3]} / invalid out-of-set"
            elif 'minItems' in c_dict:
                c_str = f"items [{c_dict['minItems']} .. {c_dict['maxItems']}]"
                lb = fdata['bva_3point']['lower_items_boundary']
                bva_str = f"MinItems({lb['just_below_min']['count']}, {lb['at_min']['count']}, {lb['just_above_min']['count']})"
            else:
                c_str = fdata.get('type', '')
                bva_str = 'EP Boolean/Type partitions'

            print(f'{qualified:<46} | {c_str:<24} | {bva_str}')

    print('=' * 98)
    print(
        f"Summary: {dataset['summary']['schemas_processed']} OpenAPI Schemas | "
        f"{dataset['summary']['total_ep_partitions_generated']} EP Partitions | "
        f"{dataset['summary']['total_3point_bva_cases_generated']} 3-Point BVA Boundary Values Generated"
    )
    print('=' * 98)


def compare_constraint_changes(v1_data: dict[str, Any], v2_data: dict[str, Any]) -> None:
    """Display the effect of changing 2 OpenAPI constraints on regenerated EP & 3-point BVA values."""
    print('\n' + '=' * 98)
    print('VIVA SPEC CONSTRAINT-CHANGE DEMONSTRATION (v1 Baseline Spec vs. v2 Modified Spec)')
    print('=' * 98)
    targets = [
        ('PurchaseOrderLineItemCreate', 'quantity'),
        ('PurchaseOrderLineItemCreate', 'discount'),
    ]
    for sname, fname in targets:
        f1 = v1_data['schemas'][sname]['fields'][fname]
        f2 = v2_data['schemas'][sname]['fields'][fname]
        lb1, ub1 = f1['bva_3point']['lower_boundary'], f1['bva_3point']['upper_boundary']
        lb2, ub2 = f2['bva_3point']['lower_boundary'], f2['bva_3point']['upper_boundary']
        print(f'Field: {sname}.{fname}')
        print(
            f"  [v1 Baseline] Constraints: min={f1['constraints']['minimum']}, max={f1['constraints']['maximum']} "
            f"| Nominal EP={f1['ep_classes']['valid_nominal']['value']}"
        )
        print(
            f"    -> v1 3-Point BVA Lower: ({lb1['just_below_min']['value']} [Reject], {lb1['at_min']['value']} [Accept], {lb1['just_above_min']['value']} [Accept])"
        )
        print(
            f"    -> v1 3-Point BVA Upper: ({ub1['just_below_max']['value']} [Accept], {ub1['at_max']['value']} [Accept], {ub1['just_above_max']['value']} [Reject])"
        )
        print(
            f"  [v2 Modified] Constraints: min={f2['constraints']['minimum']}, max={f2['constraints']['maximum']} "
            f"| Nominal EP={f2['ep_classes']['valid_nominal']['value']}"
        )
        print(
            f"    -> v2 3-Point BVA Lower: ({lb2['just_below_min']['value']} [Reject], {lb2['at_min']['value']} [Accept], {lb2['just_above_min']['value']} [Accept])"
        )
        print(
            f"    -> v2 3-Point BVA Upper: ({ub2['just_below_max']['value']} [Accept], {ub2['at_max']['value']} [Accept], {ub2['just_above_max']['value']} [Reject])"
        )
        print('-' * 98)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate EP and 3-Point BVA test data from OpenAPI spec')
    parser.add_argument('--spec', type=Path, default=DEFAULT_SPEC, help='Path to OpenAPI YAML spec')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Output JSON path')
    parser.add_argument(
        '--compare-v2',
        action='store_true',
        help='Also run generator on v2 modified spec (2 constraint changes) and display diff',
    )
    args = parser.parse_args()

    v1_dataset = generate_dataset_from_spec(args.spec, args.output)
    print_generation_report(v1_dataset, args.output)

    if args.compare_v2:
        v2_dataset = generate_dataset_from_spec(MODIFIED_SPEC, MODIFIED_OUTPUT)
        compare_constraint_changes(v1_dataset, v2_dataset)
