测试能力成熟度月报 V2.0.18
双击打开：测试能力成熟度月报.html

【落地】仓库里这份 HTML 是结构完整稿。开发机没有 5000 正式库，数字来自 18 条样例，不能当正式月报给主人。
请 @王少波 用当前 5000 正式库再生成一次后落地（18 已切就用 18 的库，不要写死 17）：

  py -3.10 generate_v2_0_18.py --db "<当前5000的 source\data\maturity.db>" --out-dir "E:\raft\monthly-reports\v2.0.18"

正式文件：E:\raft\monthly-reports\v2.0.18\测试能力成熟度月报.html
不覆盖既有 v2.0.14 / v2.0.15 月报目录。
