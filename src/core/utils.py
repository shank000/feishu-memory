"""公共工具函数"""

import re


def extract_search_keywords(query: str) -> list[str]:
    """提取搜索关键词：英文单词 + 中文2-gram + 中文单字

    用于三层记忆的关键词搜索，支持中英混合查询。
    """
    # 英文单词 (只匹配ASCII字母数字)
    en_words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', query.lower())

    # 中文连续片段
    cn_segments = re.findall(r'[\u4e00-\u9fff]+', query)

    stop = {
        '的', '了', '是', '在', '和', '与', '及', '等', '为', '中',
        '有', '用', '什么', '吗', '呢', '谁', '哪', '怎', '这', '那',
        '个', '不', '没', '还', '就', '都', '也', '要', '会', '能',
        '可', '我', '你', '他', '她',
    }

    cn_words = []
    for seg in cn_segments:
        for ch in seg:
            if ch not in stop:
                cn_words.append(ch)
        # 连续2字组合 (bigram)
        for i in range(len(seg) - 1):
            bigram = seg[i:i + 2]
            if not any(c in stop for c in bigram):
                cn_words.append(bigram)

    # 去重，优先保留长词
    seen = set()
    result = []
    for w in sorted(set(en_words + cn_words), key=len, reverse=True):
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result
