import { Alert, Card, Col, Progress, Row, Space, Statistic, Table, Tag, Typography } from 'antd'
import { Bar, Column } from '@ant-design/plots'
import { report } from './data.js'

const { Title, Paragraph, Text } = Typography

function scoreColor(score) {
  if (score >= 3) return '#1d7a35'
  if (score < 1.75) return '#a94442'
  return '#173b63'
}

function Chapter({ no, title, children }) {
  return (
    <Card
      title={
        <span>
          <Text style={{ color: '#287a8d', marginRight: 8, fontWeight: 700 }}>{no}</Text>
          {title}
        </span>
      }
    >
      {children}
    </Card>
  )
}

export default function App() {
  const domainData = report.domains.map((d) => ({ ...d, color: scoreColor(d.score) }))
  const rankData = [...report.topBottom]
    .sort((a, b) => b.score - a.score)
    .map((r) => ({ team: r.team, score: r.score, color: scoreColor(r.score) }))
  const planData = report.plan.map((p) => ({
    month: p.month,
    n: p.n,
    color: p.month === '未标记' ? '#c0392b' : '#173b63',
  }))

  const formulaCols = [
    { title: '层级', dataIndex: 'lv', width: 140 },
    { title: '权重', dataIndex: 'w', width: 180 },
    { title: '口径', dataIndex: 'rule' },
  ]
  const formulaRows = [
    { key: 1, lv: '科组–领域', w: '2级×2 + 3级 + 4级', rule: '达成率相加；5 级不计分' },
    { key: 2, lv: '科组', w: '等权', rule: '关联领域算术平均' },
    { key: 3, lv: '部门 / 中心', w: '等权', rule: '科组算术平均，非条目合并' },
  ]
  const boundCols = [
    { title: '数据项', dataIndex: 'item', width: 180 },
    { title: '来源', dataIndex: 'src', width: 180 },
    { title: '红线', dataIndex: 'line' },
  ]
  const boundRows = [
    { key: 1, item: '得分 / 排名 / 领域柱', src: 'V2.0.18 正式库', line: '禁止用样本库或估算' },
    { key: 2, item: '缺陷 / reopen', src: '库无字段', line: '仅标「临时演示」，不作结论' },
    { key: 3, item: '外部对标', src: '无核验来源', line: '本期不引用' },
  ]
  const modeCols = [
    { title: '维度', dataIndex: 'd', width: 100 },
    { title: '2025', dataIndex: 'y25' },
    { title: '2026', dataIndex: 'y26' },
  ]
  const modeRows = [
    { key: 1, d: '范围', y25: '科组自选', y26: '统一清单' },
    { key: 2, d: '目标', y25: '各自自定', y26: '统一 3.0' },
    { key: 3, d: '对比', y25: '无法横向比', y26: '同一口径可对比' },
    { key: 4, d: '跟踪', y25: '季度跟踪', y26: '实时跟踪' },
    { key: 5, d: '验收', y25: '年底集中', y26: '达成即验收' },
  ]
  const mergeCols = [
    { title: '领域', dataIndex: 'd', width: 220 },
    { title: '归并说明', dataIndex: 'n' },
  ]
  const mergeRows = [
    { key: 1, d: '软件 / 硬件 / 机械 / EMC', n: '独立计分，不归并' },
    { key: 2, d: '合规', n: '安规 / 合规 / 认证 → 合规' },
    { key: 3, d: '环境可靠性', n: '可靠性 / 环境 → 环境可靠性' },
  ]
  const rankCols = [
    { title: '档', dataIndex: 'band', width: 90 },
    { title: '科组', dataIndex: 'team' },
    { title: '得分', dataIndex: 'score', align: 'right', render: (v) => v.toFixed(2) },
    { title: '相对目标', dataIndex: 'vs', align: 'right', render: (v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2)) },
  ]

  const barCommon = {
    legend: false,
    axis: { x: { title: false }, y: { title: false } },
    label: { text: 'score', position: 'right', formatter: (v) => Number(v).toFixed(2) },
    scale: { x: { domain: [0, 4] } },
    style: { maxHeight: 22, radius: 2, fill: (d) => d.color },
  }

  return (
    <div className="page">
      <Card styles={{ body: { padding: 20 } }}>
        <Text type="secondary">TEST CAPABILITY MATURITY MONTHLY · ANTD</Text>
        <Title level={2} style={{ margin: '4px 0 8px', color: '#173b63' }}>测试能力成熟度月报</Title>
        <Paragraph type="secondary" style={{ marginBottom: 8 }}>
          报告期 {report.period}　·　口径 {report.version} 三层计分　·　年度目标 <b>{report.target.toFixed(1)}</b>　·　满分 {report.full.toFixed(1)}
          <br />
          正式库：{report.items} 项 / {report.teams} 科组 / {report.orgs} 组织　·　全中心得分 <b>{report.center.toFixed(2)}</b>（科组等权）
        </Paragraph>
        <Space wrap>
          <Tag color="success">真实库计算</Tag>
          <Tag color="warning">临时演示 · 后续替换</Tag>
          <Tag color="blue">叙述参考</Tag>
          <Tag>antd 重排 · 数字不变</Tag>
        </Space>
        <Alert
          style={{ marginTop: 12 }}
          type="info"
          showIcon
          message="本期判断"
          description={`目标 ${report.target.toFixed(1)}，现状 ${report.center.toFixed(2)}，差距 ${Math.abs(report.gap).toFixed(2)} 分，仍处「打基础」阶段。报告只讲四件事：目标、当前现状、各部门优劣势、后续改进计划。科组不列全表，只看前 5%、后 5% 与部门均值。`}
        />
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Chapter no="01" title="报告简介：目标与口径">
            <Title level={5}>1.1 目标</Title>
            <Paragraph>年度成熟度目标 <b>{report.target.toFixed(1)}</b>（满分 {report.full.toFixed(1)}），对应「3 级作为年度重点」已形成可对比的组织能力。</Paragraph>
            <Title level={5}>1.2 计分公式（V2.0.18）</Title>
            <Table size="small" pagination={false} columns={formulaCols} dataSource={formulaRows} />
            <Title level={5}>1.3 数据边界</Title>
            <Table size="small" pagination={false} columns={boundCols} dataSource={boundRows} />
          </Chapter>
        </Col>

        <Col xs={24} lg={12}>
          <Chapter no="03" title="当前现状">
            <Row gutter={12}>
              <Col span={12}><Statistic title="全中心得分 · 真实库" value={report.center} precision={2} /></Col>
              <Col span={12}><Statistic title="距年度目标" value={report.gap} precision={2} valueStyle={{ color: '#a94442' }} /></Col>
              <Col span={12}><Statistic title="能力项" value={report.items} suffix={<Text type="secondary">{report.teams} 科组 · {report.orgs} 组织</Text>} /></Col>
              <Col span={12}><Statistic title="目标达成带" value="未进" valueStyle={{ color: '#a94442' }} /></Col>
            </Row>
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">现状 {report.center.toFixed(2)} / 满分 {report.full.toFixed(1)}，红线 = 目标 {report.target.toFixed(1)}</Text>
              <Progress
                percent={(report.center / report.full) * 100}
                success={{ percent: 0 }}
                strokeColor="#287a8d"
                trailColor="#e4e9ee"
                format={() => report.center.toFixed(2)}
              />
            </div>
            <Paragraph style={{ marginTop: 8 }}>
              <b>读图：</b>{report.center.toFixed(2)} 约为满分 44%、目标 58%。多数科组仍停在 2 级基底，3/4 级贡献有限。总分是科组等权，不是条目合并。
            </Paragraph>
          </Chapter>
        </Col>

        <Col xs={24} lg={12}>
          <Chapter no="02" title="管理模式演进（2025→2026）">
            <Tag color="blue">叙述参考</Tag>
            <Paragraph style={{ marginTop: 8 }}>文字取自介绍定稿；对照数字用本期库。</Paragraph>
            <Title level={5}>2.1 痛点 → 转向</Title>
            <Table size="small" pagination={false} columns={modeCols} dataSource={modeRows} />
            <Title level={5}>2.2 六大领域（含归并）</Title>
            <Table size="small" pagination={false} columns={mergeCols} dataSource={mergeRows} />
            <Title level={5}>2.3 能力阶</Title>
            <Space wrap>
              <Tag color="cyan">2 级 · 打基础 · 本期主战场</Tag>
              <Tag color="blue">3 级 · 年度重点 · 目标线 3.0</Tag>
              <Tag>4 级 · 数字化 / AI · 5 级不计分</Tag>
            </Space>
            <Alert style={{ marginTop: 12 }} type="success" message={`对照本期：全中心 ${report.center.toFixed(2)}，距 ${report.target.toFixed(1)} 差 ${Math.abs(report.gap).toFixed(2)}。统一目标已立住，多数组织尚未把 3 级做成可验收结果。`} />
          </Chapter>
        </Col>

        <Col xs={24} lg={12}>
          <Chapter no="04" title="基准分析与改进建议">
            <Title level={5}>4.1 六领域得分（真实库 · 条形）</Title>
            <div className="chart-box">
              <Bar
                data={domainData}
                xField="score"
                yField="name"
                {...barCommon}
              />
            </div>
            <Paragraph type="secondary">满分 4.0　绿=已过 3.0　红=明显低于中心 1.75</Paragraph>
            <Title level={5}>4.2 分析</Title>
            <Paragraph>唯一过线领域是合规（3.10）。机械 1.12、环境可靠性 1.43 明显拖总分。软件 / 硬件贴近中心均值，不是杠杆。改进不能「六域平均用力」。</Paragraph>
            <Title level={5}>4.3 建议</Title>
            <ol>
              <li>锚点始终是 3.0，不用条目增量替代。</li>
              <li>1.75 阶段先保 2 级覆盖和 3 级验收，4 级不是本期杠杆。</li>
              <li>部门用本部门均值管科组；中心只盯后 5% 与最低领域。</li>
              <li>未标计划月份的未达成项不进年底预测。</li>
            </ol>
            <Alert type="warning" showIcon message={`4.4 质量结果 · 临时演示。库无缺陷 / reopen 字段。占位：平均缺陷/产品 ${report.demoQuality.defects}，reopen ${report.demoQuality.reopen}%。禁止当结论。不引用无来源行业数。`} />
          </Chapter>
        </Col>

        <Col xs={24} lg={12}>
          <Chapter no="05" title="各部门优劣势">
            <Paragraph>38 科组，5% ≈ 2 个。只保留前 5%、后 5%、部门均值。排名用条形，不用全表铺开。</Paragraph>
            <Title level={5}>5.1 前 5% / 后 5%</Title>
            <Table size="small" pagination={false} columns={rankCols} dataSource={report.topBottom.map((r, i) => ({ ...r, key: i }))} />
            <div className="chart-box">
              <Bar data={rankData} xField="score" yField="team" {...barCommon} />
            </div>
            <Paragraph>安规测试组 3.10 已过目标，主因合规领域 3.10 拉动。后 5% 工业电源测试组 0.67、人形机器人测试组 0.96，距 3.0 分别差 2.33 / 2.04。</Paragraph>
            <Title level={5}>5.2 部门均值（对标中心 {report.center.toFixed(2)}）</Title>
            <Statistic title={report.dept.name} value={report.dept.score} precision={2} />
            <Paragraph>驱动产品测试部 1.80，与组织能力概览·按部门一致。高于中心 1.75 为相对优势，距 3.0 仍差 1.20。</Paragraph>
            <Alert type="info" message="优势侧（合规、安规）把 3 级做成可验收模板。短板侧（机械领域、工业电源 / 人形机器人）90 天只打 2 级，不平行铺 4 级。" />
          </Chapter>
        </Col>

        <Col xs={24} lg={12}>
          <Chapter no="06" title="后续改进计划">
            <Title level={5}>6.1 未达成项计划月份（真实库 · 柱状）</Title>
            <div className="chart-box-sm">
              <Column
                data={planData}
                xField="month"
                yField="n"
                legend={false}
                label={{ text: 'n', position: 'top' }}
                style={{ maxWidth: 40, radiusTopLeft: 3, radiusTopRight: 3, fill: (d) => d.color }}
              />
            </div>
            <Table
              size="small"
              pagination={false}
              columns={report.plan.map((p) => ({ title: p.month, dataIndex: p.month, align: 'right' }))}
              dataSource={[{ key: 1, ...Object.fromEntries(report.plan.map((p) => [p.month, p.n])) }]}
            />
            <Paragraph><b>读图：</b>未标记 1166 项，9–12 月合计仅 3 项。未标记占比过高 → 年底摸到 3.0 的预测目前不可信，须先补计划月份。</Paragraph>
            <Title level={5}>6.2 90 天动作</Title>
            <ol>
              <li>中心：盯 1.75→2.2 的结构，每月只看后 5%、最低领域（机械）、未标记计划项。</li>
              <li>部门：低于本部门均值的科组必须有 9–12 月计划。</li>
              <li>Owner：对机械 / 环境可靠性做供给复盘，目标仍是 3.0。</li>
              <li>后 5% 科组：只承诺 90 天可验收的 2 级项。</li>
            </ol>
          </Chapter>
        </Col>

        <Col span={24}>
          <Chapter no="07" title="附录">
            <Paragraph><b>口径</b>　V2.0.18。科组–领域 = 2级达成率×2 + 3级达成率 + 4级达成率；科组 = 关联领域平均；部门 / 中心 = 科组等权。前/后 5%：38 组各取 2 个。</Paragraph>
            <Paragraph><b>边界</b>　真实库：1.75、1984、领域柱、前/后 5%、驱动产品测试部 1.80、计划月份。临时演示：仅 4.4 质量占位。不展示操作记录与全量科组名册。</Paragraph>
            <Paragraph type="secondary">测试能力成熟度月报 · 2026-09 · 内容口径 V2.0.18　|　antd 重排　|　数字来自 V2.0.18 正式库　|　禁止把临时演示当结论</Paragraph>
          </Chapter>
        </Col>
      </Row>
    </div>
  )
}
