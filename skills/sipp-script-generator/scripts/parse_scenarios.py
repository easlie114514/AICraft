#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIPP场景解析脚本
用于从txt或xlsx文件中解析多个SIPP模拟场景
"""

import json
import sys
from pathlib import Path


def parse_txt_file(file_path):
    """
    解析txt格式场景文件
    格式：场景名;主叫;被叫;服务器;时长;场景类型

    Args:
        file_path: txt文件路径

    Returns:
        list: 场景列表
    """
    scenarios = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(';')
            if len(parts) < 5:
                print(f"警告: 第{line_num}行格式不正确，跳过: {line}")
                continue

            scenario = {
                'name': parts[0].strip(),
                'caller': parts[1].strip(),
                'callee': parts[2].strip(),
                'server': parts[3].strip(),
                'duration': parts[4].strip(),
                'scenario_type': parts[5].strip() if len(parts) > 5 else 'basic_call'
            }
            scenarios.append(scenario)

    return scenarios


def parse_xlsx_file(file_path):
    """
    解析xlsx格式场景文件
    列顺序：场景名 | 主叫 | 被叫 | 服务器 | 时长 | 场景类型

    Args:
        file_path: xlsx文件路径

    Returns:
        list: 场景列表
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("需要安装openpyxl库: pip install openpyxl==1.3.0")

    scenarios = []
    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb.active

    # 跳过表头
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) > 1:
        header = rows[0]
        data_rows = rows[1:]
    else:
        data_rows = []

    for row_num, row in enumerate(data_rows, 2):
        # 跳过空行
        if not any(row):
            continue

        # 确保有足够的列
        row_values = list(row) + [''] * (6 - len(row))

        scenario = {
            'name': str(row_values[0]).strip() if row_values[0] else '',
            'caller': str(row_values[1]).strip() if row_values[1] else '',
            'callee': str(row_values[2]).strip() if row_values[2] else '',
            'server': str(row_values[3]).strip() if row_values[3] else '',
            'duration': str(row_values[4]).strip() if row_values[4] else '10',
            'scenario_type': str(row_values[5]).strip() if row_values[5] else 'basic_call'
        }

        if not scenario['name']:
            print(f"警告: 第{row_num}行缺少场景名，跳过")
            continue

        scenarios.append(scenario)

    wb.close()
    return scenarios


def parse_scenarios(file_path):
    """
    解析场景文件（自动识别格式）

    Args:
        file_path: 场景文件路径

    Returns:
        dict: {'scenarios': list, 'file_format': str}
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    file_ext = path.suffix.lower()

    if file_ext == '.txt':
        scenarios = parse_txt_file(file_path)
        file_format = 'txt'
    elif file_ext in ['.xlsx', '.xls']:
        scenarios = parse_xlsx_file(file_path)
        file_format = 'xlsx'
    else:
        raise ValueError(f"不支持的文件格式: {file_ext}，仅支持.txt和.xlsx")

    if not scenarios:
        print(f"警告: 文件中未找到有效场景: {file_path}")

    return {
        'scenarios': scenarios,
        'file_format': file_format,
        'total_count': len(scenarios)
    }


def main():
    """
    主函数
    """
    if len(sys.argv) < 2:
        print("用法: python parse_scenarios.py <场景文件路径>")
        print("支持格式: txt, xlsx")
        print("\ntxt格式示例:")
        print("场景名;主叫;被叫;服务器;时长;场景类型")
        print("basic_call_1;1000;2000;192.168.1.100;10;basic_call")
        print("\nxlsx格式示例:")
        print("列1: 场景名")
        print("列2: 主叫")
        print("列3: 被叫")
        print("列4: 服务器")
        print("列5: 时长（秒）")
        print("列6: 场景类型（可选）")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        result = parse_scenarios(file_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"错误: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
