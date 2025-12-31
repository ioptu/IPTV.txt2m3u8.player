import argparse
import sys

def _check_match(text, keyword_str):
    """
    辅助函数：检查文本是否包含指定关键字，支持 && 和 || 逻辑。
    """
    if not keyword_str or not keyword_str.strip():
        return False

    # 处理关键词中的引号，去除首尾可能存在的双引号并清理空格
    processed_keyword = keyword_str.strip().strip('"')

    if "&&" in processed_keyword:
        sub_keywords = [k.strip() for k in processed_keyword.split("&&") if k.strip()]
        return all(k in text for k in sub_keywords)
    elif "||" in processed_keyword:
        sub_keywords = [k.strip() for k in processed_keyword.split("||") if k.strip()]
        return any(k in text for k in sub_keywords)
    else:
        return processed_keyword in text

def extract_keyword_lines(filepath, extinf_and_url_keywords=None, extinf_or_url_keywords=None, no_config=False):
    """
    高级 M3U 解析器：支持多行配置、URL 容错及去重。
    :param no_config: 如果为 True，则丢弃 #EXTVLCOPT 等中间配置行。
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            # 过滤掉纯空行，并去除每行末尾换行符
            lines = [line.strip() for line in file if line.strip()]
    except Exception as e:
        print(f"错误：无法读取文件 {filepath}。原因：{e}")
        return []

    ordered_record_pairs = []
    seen_record_pairs = set()

    # 解析关键字逻辑
    kw1_and_kw2 = None
    if extinf_and_url_keywords:
        parts = [k.strip() for k in extinf_and_url_keywords.split(',')]
        if len(parts) == 2:
            if not parts[0] or not parts[1]:
                print("错误：--eandu 参数的两个关键字不能为空。")
                return []
            kw1_and_kw2 = (parts[0], parts[1])
        else:
            print("错误：--eandu 需要格式 'Keyword1,Keyword2'。")
            return []

    kw1_or_kw2 = None
    if extinf_or_url_keywords:
        parts = [k.strip() for k in extinf_or_url_keywords.split(',')]
        if len(parts) == 2:
            kw1_or_kw2 = (parts[0], parts[1])
        else:
            print("错误：--eoru 需要格式 'Keyword1,Keyword2'。")
            return []

    i = 0
    while i < len(lines):
        # 寻找记录起始点
        if lines[i].startswith('#EXTINF'):
            current_extinf = lines[i]
            current_sub_configs = []
            current_url = None
            
            # 向下探测，寻找 URL
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.startswith('#EXTINF'):
                    # 异常情况：在找到 URL 前遇见了下一个标签，说明当前频道 URL 丢失
                    break
                elif next_line.startswith('#'):
                    # 收集配置行
                    current_sub_configs.append(next_line)
                    j += 1
                else:
                    # 找到第一个非 '#' 开头的行，判定为 URL
                    current_url = next_line
                    break
            
            # 如果成功锁定了一组完整的 (EXTINF + URL)
            if current_url:
                matched = False
                if kw1_and_kw2:
                    matched = _check_match(current_extinf, kw1_and_kw2[0]) and \
                              _check_match(current_url, kw1_and_kw2[1])
                elif kw1_or_kw2:
                    matched = _check_match(current_extinf, kw1_or_kw2[0]) or \
                              _check_match(current_url, kw1_or_kw2[1])

                if matched:
                    # 根据 no_config 参数决定是否包含中间行
                    if no_config:
                        record_block = [current_extinf, current_url]
                    else:
                        record_block = [current_extinf] + current_sub_configs + [current_url]
                    
                    # 以 (EXTINF行, URL行) 作为唯一键进行去重
                    record_key = (current_extinf, current_url)
                    if record_key not in seen_record_pairs:
                        ordered_record_pairs.append(record_block)
                        seen_record_pairs.add(record_key)
                
                i = j + 1  # 移动到 URL 之后的一行
            else:
                # 丢失 URL 的频道，直接跳到下一个起始点
                i = j
        else:
            i += 1

    # 展开结果，并在每个记录块后添加空行
    result = []
    for block in ordered_record_pairs:
        result.extend(block)
        result.append("") 

    return result

def parse_arguments():
    parser = argparse.ArgumentParser(description='从M3U文件中提取包含指定关键字的记录')
    parser.add_argument('--input', required=True, help='输入M3U文件路径')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('-n', action='store_true', dest='no_config', help='只保留EXTINF和URL行，丢弃中间配置行')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--eandu', dest='extinf_and_url_keywords', help='AND模式："EXTINF关键词,URL关键词"')
    group.add_argument('--eoru', dest='extinf_or_url_keywords', help='OR模式："EXTINF关键词,URL关键词"')

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()

    # 根据参数调用函数
    if args.extinf_and_url_keywords:
        extracted_lines = extract_keyword_lines(
            args.input, 
            extinf_and_url_keywords=args.extinf_and_url_keywords,
            no_config=args.no_config
        )
        mode_str = "EXTINF和URL组合(AND)"
    else:
        extracted_lines = extract_keyword_lines(
            args.input, 
            extinf_or_url_keywords=args.extinf_or_url_keywords,
            no_config=args.no_config
        )
        mode_str = "EXTINF或URL组合(OR)"

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            for line in extracted_lines:
                f.write(line + '\n')
        
        count = sum(1 for line in extracted_lines if line.startswith('#EXTINF'))
        print(f"处理完成！成功提取 {count} 条记录。")
        if args.no_config:
            print("提示：已开启 -n 模式，丢弃了所有中间配置行。")
        print(f"模式：{mode_str}")
        print(f"结果保存至：{args.output}")
    except Exception as e:
        print(f"写入文件失败：{e}")
