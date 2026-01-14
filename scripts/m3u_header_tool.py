#!/usr/bin/env python3
"""
M3U文件头处理工具
用于处理M3U文件中的#EXTM3U行和x-tvg-url属性
"""

import argparse
import os
import sys
import re
import tempfile
import shutil

def safe_write_output(content, input_path, output_path):
    """
    安全地写入输出文件，支持同文件覆盖
    
    :param content: 要写入的内容字符串
    :param input_path: 输入文件路径
    :param output_path: 输出文件路径
    :return: (success, temp_path) 成功返回(True, None)，失败返回(False, temp_path)
    """
    # 获取绝对路径以判断是否为同一个文件
    input_abs = os.path.abspath(input_path)
    output_abs = os.path.abspath(output_path)
    is_same_file = input_abs == output_abs
    
    temp_path = None
    
    try:
        # 如果是同一个文件，先写到临时文件
        if is_same_file:
            # 在与输出文件相同目录创建临时文件
            output_dir = os.path.dirname(output_path) or '.'
            fd, temp_path = tempfile.mkstemp(
                dir=output_dir,
                suffix='.m3u',
                prefix='.tmp_',
                text=True
            )
            
            # 使用文件描述符打开文件
            out_f = os.fdopen(fd, 'w', encoding='utf-8')
        else:
            # 直接打开输出文件
            out_f = open(output_path, 'w', encoding='utf-8')
        
        # 写入数据
        with out_f:
            out_f.write(content)
        
        # 如果是同一个文件，进行原子替换
        if is_same_file:
            try:
                # Python 3.3+ 推荐使用 os.replace 实现原子替换
                os.replace(temp_path, output_path)
                temp_path = None  # 替换成功，清除临时文件引用
            except Exception as e:
                # 如果 os.replace 失败，使用 shutil.move 作为备选
                print(f"警告：原子替换失败，使用备选方案: {e}")
                shutil.move(temp_path, output_path)
                temp_path = None  # 移动成功，清除临时文件引用
        
        return True, None
        
    except Exception as e:
        print(f"写入文件失败: {e}")
        return False, temp_path

def cleanup_temp_file(temp_path):
    """
    清理临时文件
    """
    if temp_path and os.path.exists(temp_path):
        try:
            os.unlink(temp_path)
            print(f"已清理临时文件: {temp_path}")
        except Exception as e:
            print(f"警告：无法删除临时文件 {temp_path}: {e}")

def validate_arguments(input_path, output_path=None):
    """
    验证命令行参数的合理性
    
    :param input_path: 输入文件路径
    :param output_path: 输出文件路径
    :return: 验证成功返回True，失败返回False
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"错误：输入文件 '{input_path}' 不存在")
        return False
    
    # 检查输入文件是否可读
    if not os.access(input_path, os.R_OK):
        print(f"错误：输入文件 '{input_path}' 不可读")
        return False
    
    # 检查是否为文件
    if not os.path.isfile(input_path):
        print(f"错误：'{input_path}' 不是文件")
        return False
    
    # 检查输入文件扩展名（可选警告）
    if not input_path.lower().endswith('.m3u'):
        print(f"警告：输入文件 '{input_path}' 可能不是标准M3U文件")
    
    # 如果有输出文件路径，检查输出目录是否可写
    if output_path:
        output_dir = os.path.dirname(os.path.abspath(output_path)) or '.'
        if not os.access(output_dir, os.W_OK):
            print(f"错误：输出目录 '{output_dir}' 不可写")
            return False
    
    return True

def process_m3u_header(file_content, replace_value=None, force_value=None, delete_extm3u=False):
    """
    处理M3U文件内容
    
    :param file_content: 文件内容字符串
    :param replace_value: -e 参数的值，替换现有的非空x-tvg-url
    :param force_value: -E 参数的值，强制设置x-tvg-url
    :param delete_extm3u: -c 参数，删除#EXTM3U行
    :return: 处理后的文件内容
    """
    lines = file_content.splitlines()
    processed_lines = []
    
    # x-tvg-url 正则表达式
    x_tvg_url_pattern = re.compile(r'x-tvg-url="([^"]*)"')
    
    for line in lines:
        line = line.rstrip()  # 去除末尾空白
        
        # 处理 #EXTM3U 行
        if line.startswith('#EXTM3U'):
            if delete_extm3u:
                continue  # 跳过这一行（删除）
            
            # 检查是否已经有 x-tvg-url 属性
            tvg_match = x_tvg_url_pattern.search(line)
            
            if force_value is not None:
                # -E 模式：强制设置或添加 x-tvg-url
                if tvg_match:
                    # 替换现有的 x-tvg-url
                    new_line = x_tvg_url_pattern.sub(f'x-tvg-url="{force_value}"', line)
                else:
                    # 添加 x-tvg-url 属性
                    new_line = f'{line} x-tvg-url="{force_value}"'
                processed_lines.append(new_line)
                
            elif replace_value is not None:
                # -e 模式：只有当 x-tvg-url 存在且不为空时才替换
                if tvg_match:
                    current_value = tvg_match.group(1)
                    if current_value.strip():  # 如果当前值不为空
                        new_line = x_tvg_url_pattern.sub(f'x-tvg-url="{replace_value}"', line)
                    else:
                        new_line = line  # 保持原样
                else:
                    new_line = line  # 没有x-tvg-url属性，保持原样
                processed_lines.append(new_line)
                
            else:
                # 没有 -e 或 -E 参数，保持原样
                processed_lines.append(line)
                
        else:
            # 非 #EXTM3U 行，直接添加
            processed_lines.append(line)
    
    # 如果没有 #EXTM3U 行但需要添加 x-tvg-url
    if force_value is not None and not any(line.startswith('#EXTM3U') for line in processed_lines):
        # 在第一行插入 #EXTM3U 行
        processed_lines.insert(0, f'#EXTM3U x-tvg-url="{force_value}"')
    elif not any(line.startswith('#EXTM3U') for line in processed_lines) and not delete_extm3u:
        # 如果没有 #EXTM3U 行且没有删除它，添加默认的 #EXTM3U 行
        processed_lines.insert(0, '#EXTM3U')
    
    return '\n'.join(processed_lines)

def process_single_file(input_file, output_file, replace_value, force_value, delete_extm3u):
    """
    处理单个文件
    
    :return: 成功返回True，失败返回False
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        processed_content = process_m3u_header(
            content, 
            replace_value=replace_value,
            force_value=force_value,
            delete_extm3u=delete_extm3u
        )
        
        # 安全写入输出文件
        success, temp_path = safe_write_output(processed_content, input_file, output_file)
        
        if not success:
            cleanup_temp_file(temp_path)
            return False
        
        return True
        
    except Exception as e:
        print(f"处理文件 '{input_file}' 时发生错误: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="M3U文件头处理工具",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
示例:
  # 多个文件逐个处理（原地修改）
  python m3u_header.py -i file1.m3u file2.m3u -e "http://example.com/epg.xml"
  
  # 单个文件输出到新文件
  python m3u_header.py -i input.m3u -o output.m3u -E "http://new-epg.com/epg.xml"
  
  # 强制设置x-tvg-url并删除#EXTM3U行（矛盾操作，会先删除再添加）
  python m3u_header.py -i playlist.m3u -E "http://epg.com/epg.xml" -c
        """
    )
    
    parser.add_argument(
        '-i', '--input', 
        nargs='+', 
        required=True,
        help='输入M3U文件路径（可以是一个或多个文件）'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='输出文件路径（使用此参数时，-i只能指定一个文件）'
    )
    
    parser.add_argument(
        '-e', '--replace',
        help='替换现有的非空x-tvg-url属性值为指定值\n格式: "http://example.com/epg.xml"'
    )
    
    parser.add_argument(
        '-E', '--force',
        help='强制设置x-tvg-url属性值为指定值，没有则添加\n格式: "http://example.com/epg.xml"'
    )
    
    parser.add_argument(
        '-c', '--clean',
        action='store_true',
        help='删除#EXTM3U行'
    )
    
    parser.add_argument(
        '--force-overwrite',
        action='store_true',
        help='强制覆盖输出文件（如果已存在且与输入不同）'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细处理信息'
    )
    
    args = parser.parse_args()
    
    # 参数验证
    if args.replace and args.force:
        print("错误：不能同时使用 -e 和 -E 参数")
        sys.exit(1)
    
    if args.output and len(args.input) > 1:
        print("错误：使用 -o 参数时，-i 只能指定一个文件")
        sys.exit(1)
    
    # 检查所有输入文件
    for input_file in args.input:
        if not os.path.exists(input_file):
            print(f"错误：输入文件 '{input_file}' 不存在")
            sys.exit(1)
    
    # 处理逻辑
    success_count = 0
    failed_count = 0
    
    if args.output:
        # 单个文件输出模式
        input_file = args.input[0]
        output_file = args.output
        
        if not validate_arguments(input_file, output_file):
            sys.exit(1)
        
        # 检查输出文件是否已存在且与输入不同
        input_abs = os.path.abspath(input_file)
        output_abs = os.path.abspath(output_file)
        
        if os.path.exists(output_file) and input_abs != output_abs:
            if not args.force_overwrite:
                print(f"错误：输出文件 '{output_file}' 已存在")
                print("使用 --force-overwrite 参数强制覆盖，或指定不同的输出文件")
                sys.exit(1)
        
        if args.verbose:
            print(f"处理文件: {input_file} -> {output_file}")
        
        if process_single_file(input_file, output_file, args.replace, args.force, args.clean):
            success_count += 1
            if args.verbose:
                print(f"  成功")
        else:
            failed_count += 1
            if args.verbose:
                print(f"  失败")
    
    else:
        # 多个文件原地修改模式
        for input_file in args.input:
            output_file = input_file  # 原地修改
            
            if not validate_arguments(input_file):
                continue
            
            if args.verbose:
                print(f"处理文件: {input_file}")
            
            if process_single_file(input_file, output_file, args.replace, args.force, args.clean):
                success_count += 1
                if args.verbose:
                    print(f"  成功")
            else:
                failed_count += 1
                if args.verbose:
                    print(f"  失败")
    
    # 输出统计信息
    print(f"\n处理完成!")
    print(f"成功: {success_count} 个文件")
    print(f"失败: {failed_count} 个文件")
    
    if args.verbose:
        print(f"\n操作摘要:")
        if args.replace:
            print(f"  - 替换非空x-tvg-url: {args.replace}")
        if args.force:
            print(f"  - 强制设置x-tvg-url: {args.force}")
        if args.clean:
            print(f"  - 删除#EXTM3U行: 是")
        else:
            print(f"  - 删除#EXTM3U行: 否")
        
        if args.output:
            print(f"  - 输出模式: 单个文件输出")
        else:
            print(f"  - 输出模式: 多个文件原地修改")
    
    if failed_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
