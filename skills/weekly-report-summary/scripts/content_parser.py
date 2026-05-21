# -*- coding: utf-8 -*-
"""
内容解析模块

解析周报邮件正文，提取结构化内容
"""

import re
from typing import Dict, List, Optional, Tuple

import config

SECTION_LABELS = {
    'this_week_work': '本周完成工作',
    'next_week_plan': '下周工作计划',
    'gains_losses': '本周得与失',
    'praise': '事迹点赞',
    'suggestions': '诚信坦荡',
}

PERSONAL_SECTION_KEYS = (
    'this_week_work',
    'next_week_plan',
    'gains_losses',
    'praise',
)


def normalize_section_key(section_key: str) -> str:
    """规范化标准区块键，不支持时返回空字符串。"""
    key = (section_key or '').strip()
    return key if key in SECTION_LABELS else ''


def get_section_label(section_key: str) -> str:
    """获取标准区块键对应的中文标题。"""
    return SECTION_LABELS.get(section_key, section_key)


def extract_praise_from_body(body: str) -> str:
    """
    从邮件正文中提取点赞内容
    
    点赞内容特征：
    - 位于 "事迹推车" 和 "诚信坦荡" 之间
    - 包含 "感谢" 或 "点赞" 关键词
    - 格式通常是 "感谢@xxx" 或 "点赞@xxx"
    """
    lines = body.split('\n')
    
    praise_lines = []
    in_praise_section = False
    
    for line in lines:
        line_stripped = line.strip()
        
        # 检测进入点赞区域
        if '事迹推车' in line_stripped or '事迹点赞' in line_stripped:
            in_praise_section = True
            continue
        
        # 检测离开点赞区域（包括各种可能的结束标记）
        if in_praise_section:
            end_markers = ['诚信坦荡', '工作复盘', '本周完成工作', '本周工作回顾',
                          '方向', '建议人', '@ta推进', '存在问题', '建设性意见']
            if any(marker in line_stripped for marker in end_markers):
                in_praise_section = False
                continue
        
        # 收集点赞内容
        if in_praise_section and line_stripped:
            # 只保留包含"感谢"或"点赞"的行，或者以@开头的行
            if ('感谢' in line_stripped or '点赞' in line_stripped or 
                line_stripped.startswith('@') or '@' in line_stripped):
                # 过滤掉模板占位内容
                if not is_praise_template_content(line_stripped):
                    praise_lines.append(line_stripped)
    
    return '\n'.join(praise_lines)


def is_praise_template_content(text: str) -> bool:
    """
    检查是否是点赞区域的模板占位内容
    """
    template_markers = [
        '关键词', '事迹推车', '事迹点赞', '协同', '专业', '突破',
        '@ta推进', '建议人', '存在问题',
        # 模板中的占位文本
        '相信@ta可推进', '相信@ta可推进', 
        '方向', '存在问题', '建设性意见与措施',
        '降本增效', '协同攻坚', '高质量发展',
        '部门协同', '提升专业', '其他',
    ]
    
    text_stripped = text.strip()
    
    for marker in template_markers:
        if text_stripped == marker:
            return True
    
    # 检查是否只包含 "相信@ta可推进" 这类占位内容
    if '相信@ta可推进' in text_stripped:
        return True
    
    return False


def parse_weekly_report_content(body: str, skip_signature: bool = True) -> Dict[str, str]:
    """
    解析周报正文，提取各部分内容
    
    Returns:
        字典包含：
        - this_week_work: 本周完成工作
        - next_week_plan: 下周工作计划
        - gains_losses: 本周得与失
        - praise: 点赞/感谢内容（星光闪烁部分）
        - suggestions: 建议内容（诚信坦荡部分）
    """
    result = {
        'this_week_work': '',
        'next_week_plan': '',
        'gains_losses': '',
        'praise': '',
        'suggestions': '',
        'raw_body': body  # 保留原始内容以备用
    }
    
    # 清理正文
    body = body.strip()
    
    # === 特殊处理：提取点赞内容 ===
    # 点赞内容在 "事迹推车" 和 "诚信坦荡" 之间，包含 "感谢" 或 "点赞" 的行
    result['praise'] = extract_praise_from_body(body)
    
    # 定义各部分的标记
    # 注意：长模式需要放在前面，避免短模式误匹配
    # 例如 "本周得与失" 应该匹配 gains_losses，而不是被 "本周" 匹配到 this_week_work
    section_patterns = {
        'gains_losses': [
            # gains_losses 放在最前面，避免被 "本周" 误匹配
            r'本周得与失[：:\s]*',
            r'其他收获与思考[：:\s]*',
            r'得与失[：:\s]*',
            r'收获与思考[：:\s]*',
        ],
        'this_week_work': [
            r'本周完成工作[：:\s]*',
            r'本周工作回顾[：:\s]*',
            r'本周完成[：:\s]*',
            r'本周工作[：:\s]*',
            # 短标题：必须是独立一行，后面紧跟冒号或换行，使用负向前瞻确保不会匹配到 "本周得与失"
            r'(?:^|\n)本周(?!得与失|挺|很|还|不)[：:\n]\s*',
        ],
        'next_week_plan': [
            r'下周工作计划[：:\s]*',
            r'下周完成工作[：:\s]*',
            r'下周工作[：:\s]*',
            r'下周计划[：:\s]*',
            # 短标题：必须是独立一行，后面紧跟冒号或换行
            r'(?:^|\n)下周[：:\n]\s*',
        ],
        'praise': [
            # 点赞内容已在前面通过 extract_praise_from_body 专门提取，不再使用正则
            # 避免覆盖正确的提取结果
        ],
        'suggestions': [
            # 建议部分暂时不自动解析，格式复杂
        ]
    }
    
    # 构建所有可能的分隔符模式
    all_patterns = []
    for patterns in section_patterns.values():
        all_patterns.extend(patterns)
    
    # 找到所有匹配的位置
    matches = []
    for section_name, patterns in section_patterns.items():
        for pattern in patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                matches.append({
                    'section': section_name,
                    'start': match.start(),
                    'end': match.end(),
                    'pattern': pattern
                })
    
    # 按位置排序
    matches.sort(key=lambda x: x['start'])
    
    # 去除重叠的匹配：当多个匹配起始位置相近时，只保留结束位置最远的（最长匹配）
    filtered_matches = []
    for match in matches:
        # 检查是否与已保留的匹配重叠
        is_overlapping = False
        for i, existing in enumerate(filtered_matches):
            # 如果当前匹配的起始位置在已有匹配的范围内，说明重叠
            if existing['start'] <= match['start'] < existing['end']:
                is_overlapping = True
                # 如果当前匹配更长（结束位置更远），替换已有的
                if match['end'] > existing['end']:
                    filtered_matches[i] = match
                break
        
        if not is_overlapping:
            filtered_matches.append(match)
    
    matches = filtered_matches
    
    # 提取各部分内容
    for i, match in enumerate(matches):
        section_name = match['section']
        content_start = match['end']
        
        # 内容结束位置是下一个匹配的开始，或者文本末尾
        if i + 1 < len(matches):
            content_end = matches[i + 1]['start']
        else:
            content_end = len(body)
        
        content = body[content_start:content_end].strip()
        
        # 清理内容（传入部分类型以区分处理）
        content = clean_content(
            content,
            section_type=section_name,
            skip_signature=skip_signature,
        )
        
        # 如果该部分还没有内容，或新内容更长，则更新
        if not result[section_name] or len(content) > len(result[section_name]):
            result[section_name] = content
    
    # 如果没有找到结构化内容，尝试简单分段
    if not any([result['this_week_work'], result['next_week_plan'], result['gains_losses']]):
        result = parse_simple_format(body)
        result['raw_body'] = body
    
    return result


def parse_simple_format(body: str) -> Dict[str, str]:
    """
    解析简单格式的周报（没有明确标记的情况）
    """
    result = {
        'this_week_work': '',
        'next_week_plan': '',
        'gains_losses': '',
        'praise': '',
        'suggestions': '',
    }
    
    # 按行分析
    lines = body.split('\n')
    
    # 寻找可能的分段
    current_section = 'this_week_work'
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检测是否是新的段落标记
        lower_line = line.lower()
        
        if '下周' in line or 'next week' in lower_line:
            if current_content:
                result[current_section] = '\n'.join(current_content)
            current_section = 'next_week_plan'
            current_content = []
            # 如果这行本身包含内容，加入
            content = re.sub(r'^.*?(下周工作计划|下周计划)[：:]*', '', line).strip()
            if content:
                current_content.append(content)
        elif '得与失' in line or '收获' in line or '思考' in line:
            if current_content:
                result[current_section] = '\n'.join(current_content)
            current_section = 'gains_losses'
            current_content = []
            content = re.sub(r'^.*?(得与失|收获与思考)[：:]*', '', line).strip()
            if content:
                current_content.append(content)
        else:
            current_content.append(line)
    
    # 保存最后一部分
    if current_content:
        result[current_section] = '\n'.join(current_content)
    
    return result


def remove_email_signature(content: str) -> str:
    """
    移除邮件签名
    
    常见签名特征：
    - "Best regards" / "此致" / "祝好"
    - 包含手机号、邮箱、网址、传真
    - "发自我的iPhone" 等
    - 公司名称和地址
    """
    if not content:
        return ''
    
    lines = content.split('\n')
    
    # 签名开始标记（匹配到这些后，后面的内容全部丢弃）
    signature_markers = [
        r'^-{2,}',  # -- 分隔线
        r'^_{2,}',  # __ 分隔线
        r'^={2,}',  # == 分隔线
        r'^Best\s*regards',
        r'^Regards',
        r'^Thanks',
        r'^此致',
        r'^祝好',
        r'^发自我的',
        r'^Sent from',
        r'^Get Outlook',
        r'^\s*--\s*$',
        r'^Fax[：:]',  # 传真开头（支持中英文冒号）
        r'^Tel[：:]',  # 电话开头
        r'^Mob[：:]',  # 手机号开头
        r'^Mobile[：:]',
        r'^Phone[：:]',
    ]
    
    # 签名内容特征（单行匹配，遇到就删除该行）
    signature_content_patterns = [
        r'Mob[：:]\s*\d',  # 手机号（支持中英文冒号）
        r'Tel[：:]\s*\d',  # 电话
        r'Fax[：:]\s*\d',  # 传真
        r'Web[：:]\s*www\.',  # 网址
        r'Email[：:]\s*\S+@',  # 邮箱
        r'@\S+\.com',  # 邮箱地址
        r'www\.\S+\.(com|cn|org)',  # 网址
        r'^\s*[\w\u4e00-\u9fa5]+[（(][\w\u4e00-\u9fa5]+[)）]\s*/\s*\w+',  # "花名（真名）/ 职位"
        r'^\s*[\u4e00-\u9fa5]{2,4}\s*/\s*[\u4e00-\u9fa5]+主管',  # "花名 / XX主管"
        r'杭州.*科技.*公司',  # 公司名
        r'杭州市.*路.*号',  # 地址
        r'^\d{3,4}[-\s]?\d{3,4}[-\s]?\d{4}$',  # 纯电话号码
        r'^\d{11}$',  # 手机号
        r'创伟科技园',  # 办公地址
        r'聚工路',  # 办公地址
        r'甘之草',  # 公司名
        r'gancao\.com',  # 公司域名
    ]
    
    cleaned_lines = []
    in_signature = False
    
    for line in lines:
        stripped = line.strip()
        
        # 检查是否进入签名区域
        if not in_signature:
            for marker in signature_markers:
                if re.match(marker, stripped, re.IGNORECASE):
                    in_signature = True
                    break
        
        # 如果已在签名区域，跳过
        if in_signature:
            continue
        
        # 检查是否是签名内容行
        is_signature_line = False
        for pattern in signature_content_patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                is_signature_line = True
                break
        
        if not is_signature_line:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def normalize_work_items(content: str, is_gains_losses: bool = False) -> str:
    """
    统一工作项格式为 "1. xxx" 格式
    
    Args:
        content: 原始内容
        is_gains_losses: 是否是"本周得与失"部分（不需要序号）
    """
    if not content:
        return ''
    
    lines = content.split('\n')
    result_lines = []
    
    # 本周得与失不做序号处理，但要清理无用字符
    if is_gains_losses:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 移除开头的特殊符号
            line = re.sub(r'^[\s]*[-•·*▪▸►]+[\s]*', '', line)
            if line:
                result_lines.append(line)
        return '\n'.join(result_lines)
    
    # 工作项处理
    item_index = 1
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 移除已有的各种序号格式，统一处理
        # 匹配: "1." "1、" "1)" "(1)" "①" "-" "•" "·" "*" 等
        cleaned_line = re.sub(
            r'^[\s]*'  # 前导空白
            r'('
            r'\d+[\.\、\)\]\:：]'  # 1. 1、 1) 1] 1: 1：
            r'|[（\(]\d+[）\)]'  # (1) （1）
            r'|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]'  # 圆圈数字
            r'|[-•·*▪▸►]'  # 各种符号
            r')'
            r'[\s]*',  # 后续空白
            '',
            line
        )
        
        # 如果清理后有内容，添加标准序号
        if cleaned_line:
            result_lines.append(f"{item_index}. {cleaned_line}")
            item_index += 1
    
    return '\n'.join(result_lines)


def clean_content(content: str, section_type: str = '', skip_signature: bool = True) -> str:
    """
    清理内容文本
    
    Args:
        content: 原始内容
        section_type: 部分类型（this_week_work/next_week_plan/gains_losses）
    """
    if not content:
        return ''
    
    # 先移除邮件签名
    if skip_signature:
        content = remove_email_signature(content)
    
    # 移除多余的空白行
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        # 跳过空行
        if not line:
            continue
        
        cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # 根据部分类型处理格式
    is_gains_losses = section_type == 'gains_losses'
    content = normalize_work_items(content, is_gains_losses)
    
    return content


def should_skip_email(sender_name: str, subject: str) -> bool:
    """
    检查邮件是否应该被跳过
    
    跳过条件：
    - 发件人是 wangp（发送的都是部门汇总，不是个人周报）
    - 转发的邮件
    - 其他部门的周报
    """
    # 过滤特定发件人
    skip_senders = ['wangp']
    if sender_name in skip_senders:
        return True
    
    if not subject:
        return False
    
    # 检查转发标记
    forward_markers = ['转发', 'Fwd:', 'Fw:', 'FW:']
    for marker in forward_markers:
        if marker in subject:
            return True
    
    # 检查是否是其他部门的周报（不是厚朴汤的）
    other_departments = [
        '理中汤', '修合汤', '仓廪汤', '安心汤', '建瓴汤', 
        '天雄汤', '六合汤', '拨云汤', '甘草慧养', '供应链组',
        '南极星'
    ]
    for dept in other_departments:
        if dept in subject:
            return True
    
    return False


def organize_reports_by_name(reports: List[Dict]) -> Dict[str, Dict]:
    """
    按花名整理周报内容
    
    Args:
        reports: 邮件列表（来自 email_fetcher）
        
    Returns:
        {花名: {parsed_content}}
    """
    from email_fetcher import normalize_sender_name
    
    organized = {}
    
    for report in reports:
        subject = report.get('subject', '')
        raw_name = report['sender_name']
        
        # 过滤不需要的邮件（wangp、转发邮件、其他部门周报）
        if should_skip_email(raw_name, subject):
            continue
        
        # 规范化花名
        name = normalize_sender_name(raw_name)
        
        # 解析内容
        parsed = parse_weekly_report_content(report['body'])
        parsed['sender_email'] = report['sender_email']
        parsed['subject'] = report['subject']
        parsed['date'] = report['date']
        parsed['original_name'] = raw_name
        
        # 检查内容是否有效（不是模板占位内容）
        is_valid_content = has_valid_content(parsed)
        
        # 如果同一个人有多封邮件
        if name in organized:
            existing = organized[name]
            existing_valid = has_valid_content(existing)
            
            # 优先保留有有效内容的邮件
            if is_valid_content and not existing_valid:
                # 新邮件有效，旧邮件无效，替换
                organized[name] = parsed
            elif not is_valid_content and existing_valid:
                # 新邮件无效，旧邮件有效，保留旧的
                pass
            else:
                # 都有效或都无效，保留新的（后发的）
                print(f"警告: {name} 有多封周报邮件，保留内容更完整的一封")
                if content_length(parsed) > content_length(existing):
                    organized[name] = parsed
        else:
            organized[name] = parsed
        
    return organized


def has_valid_content(parsed: Dict) -> bool:
    """检查解析结果是否有有效内容（不是XXX模板）"""
    work = parsed.get('this_week_work', '')
    plan = parsed.get('next_week_plan', '')
    
    # 如果主要内容包含XXX，认为无效
    if 'XXX' in work or 'XXX' in plan:
        return False
    
    # 如果工作内容为空或太短，认为无效
    if len(work) < 10:
        return False
    
    return True


def content_length(parsed: Dict) -> int:
    """计算内容总长度"""
    return (len(parsed.get('this_week_work', '')) + 
            len(parsed.get('next_week_plan', '')) +
            len(parsed.get('gains_losses', '')))


def group_reports_by_team(organized_reports: Dict[str, Dict]) -> Dict[str, Dict[str, Dict]]:
    """
    按组分类周报
    
    Returns:
        {组名: {花名: parsed_content}}
    """
    grouped = {group: {} for group in config.GROUP_MEMBERS.keys()}
    grouped['未分组'] = {}
    
    for name, content in organized_reports.items():
        group = config.MEMBER_TO_GROUP.get(name)
        
        if group:
            grouped[group][name] = content
        else:
            grouped['未分组'][name] = content
            print(f"警告: {name} 未在配置中找到所属组")
    
    return grouped


def extract_praise_content(organized_reports: Dict[str, Dict]) -> List[Dict]:
    """
    提取所有人的点赞/感谢内容（星光闪烁部分）
    
    Returns:
        [{name, content}, ...]
    """
    praises = []
    
    for name, content in organized_reports.items():
        if content.get('praise'):
            praises.append({
                'name': name,
                'content': content['praise']
            })
    
    return praises


def extract_suggestions_from_body(body: str) -> Dict[str, str]:
    """
    从邮件正文中提取建议内容（诚信坦荡部分）
    
    Returns:
        {
            'direction': '降本增效/协同攻坚/高质量发展',
            'problem': '存在问题',
            'suggestion': '建设性意见与措施',
            'target': '@ta推进'
        }
    """
    lines = body.split('\n')
    
    result = {
        'direction': '',
        'problem': '',
        'suggestion': '',
        'target': ''
    }
    
    in_suggestion_section = False
    current_direction = ''
    
    # 模板标签（需要跳过）
    template_labels = [
        '方向', '建议人', '@ta推进', '@部门推进', '存在问题', '建设性意见与措施',
        '降本增效', '协同攻坚', '高质量发展', '高质量', '发展',
        '部门协同', '提升专业', '其他',
        '诚信坦荡', '我想听你说'
    ]
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        # 清理零宽字符
        line_stripped = line_stripped.replace('\u200d', '').replace('\u200b', '').strip()
        
        # 检测进入建议区域
        if '诚信坦荡' in line_stripped:
            in_suggestion_section = True
            continue
        
        # 检测离开建议区域
        if in_suggestion_section and ('工作复盘' in line_stripped or '本周完成工作' in line_stripped):
            break
        
        if not in_suggestion_section:
            continue
        
        # 跳过空行和模板标签
        if not line_stripped or line_stripped in template_labels:
            continue
        
        # 记录方向
        if line_stripped in ['降本增效', '协同攻坚', '高质量发展']:
            current_direction = line_stripped
            continue
        
        # 收集有意义的建议内容
        # 如果内容不是模板占位符，则记录
        if not is_suggestion_template_content(line_stripped):
            if current_direction and not result['direction']:
                result['direction'] = current_direction
            
            # 尝试识别内容类型
            # 注意：@ta推进 和 @部门推进 是模板内容，不是真正的@人
            if '@' in line_stripped and not result['target']:
                # 确保不是模板占位符
                if line_stripped not in ['@ta推进', '@部门推进']:
                    result['target'] = line_stripped
            elif not result['problem']:
                result['problem'] = line_stripped
            elif not result['suggestion']:
                result['suggestion'] = line_stripped
    
    return result


def is_suggestion_template_content(text: str) -> bool:
    """
    检查是否是建议区域的模板占位内容
    """
    template_markers = [
        '方向', '建议人', '@ta推进', '@部门推进', '存在问题', '建设性意见与措施',
        '降本增效', '协同攻坚', '高质量发展', '高质量', '发展',
        '部门协同', '提升专业', '其他',
        '相信@ta可推进', 'XXX', 'XXXXXX'
    ]
    
    # 清理零宽字符和空白
    text_stripped = text.strip()
    # 移除零宽字符
    text_stripped = text_stripped.replace('\u200d', '').replace('\u200b', '').strip()
    
    # 如果清理后为空，认为是无效内容
    if not text_stripped:
        return True
    
    # 如果内容太短（只有1-2个字符），可能是无效内容
    if len(text_stripped) <= 2:
        return True
    
    for marker in template_markers:
        if text_stripped == marker:
            return True
    
    # 检查是否只包含占位内容
    if '相信@ta可推进' in text_stripped:
        return True
    if text_stripped.startswith('XXX'):
        return True
    
    return False


def extract_all_suggestions(organized_reports: Dict[str, Dict]) -> List[Dict]:
    """
    提取所有人的建议内容
    
    Returns:
        [{name, direction, problem, suggestion, target}, ...]
    """
    suggestions = []
    
    for name, content in organized_reports.items():
        raw_body = content.get('raw_body', '')
        if not raw_body:
            continue
        
        suggestion_data = extract_suggestions_from_body(raw_body)
        
        # 只有当有实际建议内容时才添加
        if suggestion_data.get('problem') or suggestion_data.get('suggestion'):
            suggestion_data['name'] = name
            suggestions.append(suggestion_data)
    
    return suggestions


if __name__ == "__main__":
    # 测试解析
    test_body = """
本周完成工作
1. 完成了功能A的开发
2. 修复了Bug B
3. 参加了代码评审

下周工作计划
1. 继续功能C的开发
2. 性能优化

本周得与失
本周学习了新技术，但时间管理还需要改进。
    """
    
    result = parse_weekly_report_content(test_body)
    print("解析结果:")
    for key, value in result.items():
        if key != 'raw_body':
            print(f"\n=== {key} ===")
            print(value)
