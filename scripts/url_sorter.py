import argparse
import sys
import re

def sort_m3u_urls(input_file, output_file, keywords_str, reverse_mode=False, target_channels_str=None, new_name=None):
    # 1. 初始化解析关键字
    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
    target_channels = [c.strip() for c in target_channels_str.split(',') if c.strip()] if target_channels_str else None
    
    # 2. 读取文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: 找不到文件 '{input_file}'")
        return
    except Exception as e:
        print(f"Error: 读取文件失败: {e}")
        return

    # 3. 解析 M3U
    processed_content = []
    start_index = 0
    # 兼容某些带 BOM 的 UTF-8 文件
    if lines and '#EXTM3U' in lines[0]:
        processed_content.append(lines[0].strip())
        start_index = 1

    channels_data = []
    current_inf = None
    current_urls = []

    for line in lines[start_index:]:
        line = line.strip()
        if not line: continue
        
        if line.startswith('#EXTINF'):
            if current_inf:
                channels_data.append({"inf": current_inf, "urls": current_urls})
            current_inf = line
            current_urls = []
        elif not line.startswith('#'): # 识别 URL（非 # 开头的行）
            current_urls.append(line)
        else:
            # 兼容处理：如果是其他 # 开头的辅助信息（如 #EXTGRP），暂存入 current_urls 保持结构
            current_urls.append(line)
    
    if current_inf:
        channels_data.append({"inf": current_inf, "urls": current_urls})

    # 4. 排序权重算法（大小写敏感）
    def get_sort_score(item):
        # 仅对 URL 类型的行进行关键字打分，非 URL 行保持原位
        if "://" not in item:
            return 9999 # 辅助行排在最后或保持原样
            
        for index, kw in enumerate(keywords):
            if kw in item:
                return (index + 1) if reverse_mode else (index - len(keywords))
        return 0

    # 5. 重命名算法（同步修改 tvg-name 和显示名）
    def rename_inf(inf_line, name):
        # 修改 tvg-name 属性
        if 'tvg-name="' in inf_line:
            inf_line = re.sub(r'tvg-name="[^"]*"', f'tvg-name="{name}"', inf_line)
        # 修改末尾显示名
        if ',' in inf_line:
            parts = inf_line.rsplit(',', 1)
            return f"{parts[0]},{name}"
        return f"{inf_line},{name}"

    # 6. 写入输出
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            if processed_content:
                f.write(processed_content[0] + '\n')
            
            for ch in channels_data:
                # 检查是否命中目标频道
                is_target = any(tc in ch["inf"] for tc in target_channels) if target_channels else False
                
                final_inf = rename_inf(ch["inf"], new_name) if (is_target and new_name) else ch["inf"]
                f.write(final_inf + '\n')
                
                # 确定是否排序：如果指定了 -ch 则仅对匹配项排序；若未指定则全局排
                should_sort = is_target if target_channels else True
                
                if should_sort and ch["urls"]:
                    # 使用稳定排序
                    sorted_list = sorted(ch["urls"], key=get_sort_score)
                    for item in sorted_list:
                        f.write(item + '\n')
                else:
                    for item in ch["urls"]:
                        f.write(item + '\n')
                        
        print(f"任务完成！输出至: {output_file}")
    except Exception as e:
        print(f"Error: 写入文件失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="M3U 频道排序与重命名工具")
    parser.add_argument("-i", "--input", required=True, help="输入路径")
    parser.add_argument("-o", "--output", default="output.m3u", help="输出路径")
    parser.add_argument("-k", "--keywords", required=True, help="URL 排序关键字 (大小写敏感)")
    parser.add_argument("-r", "--reverse", action="store_true", help="反向模式 (匹配项放最后)")
    parser.add_argument("-ch", "--channels", help="目标频道过滤 (支持多个，逗号分隔)")
    parser.add_argument("-rn", "--rename", help="重命名目标频道 (同步修改 tvg-name)")

    args = parser.parse_args()
    sort_m3u_urls(args.input, args.output, args.keywords, args.reverse, args.channels, args.rename)

if __name__ == "__main__":
    main()
