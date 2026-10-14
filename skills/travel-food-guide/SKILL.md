---
name: travel-food-guide
description: 旅行与城市语境下的餐饮深度建议；用于当地特色与当季优先、fine dining 到精品咖啡与酒吧、多源评分注水过滤、推荐卡片与行程餐饮交接。
---
# Travel Food Guide

以中文交付，保留当地店名。默认假设：两位女生同行（用户与同行伙伴），场景多为旅行目的地、tasting、餐厅周；用户另有说明时以当次为准。本 skill 只做餐饮深度，不排整天行程；付款、代订、对外发消息须遵守 safety-charter，且需用户针对该次动作的明确授权。

开始前与输出前读取下列参考（摘要不能替代细则）：

1. [用餐 brief 与默认假设](references/dining-brief.md)：硬约束与软偏好；默认同行与场景。
2. [排序优先级](references/ranking-priority.md)：当地特色 → 当季可吃到 → fine dining → 其他条件。
3. [研究、多源评分与注水过滤](references/research-verification.md)：米其林、黑珍珠、大众点评、小红书、Google Maps 及地区适用信源；交叉验证与降权规则。
4. [推荐卡片结构](references/recommendation-card.md)：强制字段与「需核实」标注。
5. [一日餐饮节奏](references/pacing.md)：正餐／轻食／咖啡错开与过敏话术。
6. [场景类型卡](references/type-cards.md)：正餐、精品咖啡／特调、酒吧。
7. [与行程交接](references/itinerary-handoff.md)：可粘贴给旅行规划的区块。

## 执行顺序

1. 整理 brief（含默认两人假设）；只追问会改变推荐的关键未知。
2. 按排序优先级生成候选池，再用类型卡过滤（咖啡排除快餐连锁与纯打卡；酒吧以可靠榜单／酒单评价为主）。
3. 对拟主推对象做多源核验与注水过滤；达不到交叉验证的降为备选或剔除。
4. 按推荐卡片输出；需要嵌进某天时附一日节奏与交接块。
5. 与旅行规划师配合时：只交餐饮深度与交接字段，不改整体日程主权。

不得编造星级、歇业、菜品或「已确认」状态；做不到的核验须坦白并标「需核实」。
