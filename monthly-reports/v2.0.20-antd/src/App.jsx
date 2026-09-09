import { Alert, Card, Col, Progress, Row, Space, Statistic, Table, Tag, Typography } from 'antd'
import { Bar } from '@ant-design/plots'
import { report } from './data.js'

const { Title, Paragraph, Text } = Typography

function scoreColor(score) {
  if (score == null) return '#8a96a3'
  if (score >= 3) return '#1d7a35'
  if (score < 1.75) return '#a94442'
  return '#173b63'
}

function gapText(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (n > 0) return `+${n.toFixed(2)}`
  return n.toFixed(2)
}

function scoreText(v) {
  return v == null ? '—' : Number(v).toFixed(2)
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
  const deptData = report.depts.map((d) => ({ name: d.name, score: d.score, color: scoreColor(d.score) }))
  const teamRankData = [...report.teamsListed]
    .sort((a, b) => b.score - a.score)
    .map((r) => ({ team: r.team, score: r.score, color: scoreColor(r.score) }))
  const domainBelow = report.domains.filter((d) => d.score < report.target)
  const domainAbove = report.domains.filter((d) => d.score >= report.target)

  const barCommon = {
    legend: false,
    axis: { x: { title: false }, y: { title: false } },
    label: { text: 'score', position: 'right', formatter: (v) => Number(v).toFixed(2) },
    scale: { x: { domain: [0, 4] } },
    style: { maxHeight: 22, radius: 2, fill: (d) => d.color },
  }

  const deptCols = [
    { title: '部门', dataIndex: 'name' },
    { title: '得分', dataIndex: 'score', align: 'right', width: 80, render: scoreText },
    { title: '相对中心', dataIndex: 'vsCenter', align: 'right', width: 90, render: gapText },
    { title: '距目标', dataIndex: 'vsTarget', align: 'right', width: 90, render: gapText },
    {
      title: '高低',
      dataIndex: 'vsCenter',
      key: 'band',
      width: 110,
      render: (v) => (v > 0 ? <Tag color="success">高于中心</Tag> : <Tag color="error">低于中心</Tag>),
    },
    { title: '可计分科组', dataIndex: 'scoredTeams', width: 110, render: (_, r) => `${r.scoredTeams}/${r.teamCount}` },
  ]

  const teamCols = [
    { title: '科组', dataIndex: 'team' },
    { title: '得分', dataIndex: 'score', align: 'right', width: 80, render: scoreText },
    { title: '距目标', dataIndex: 'vs', align: 'right', width: 90, render: gapText },
    { title: '短板', dataIndex: 'weak' },
  ]

  const rankCols = [
    { title: '档', dataIndex: 'band', width: 90 },
    { title: '科组', dataIndex: 'team' },
    { title: '部门', dataIndex: 'dept' },
    { title: '得分', dataIndex: 'score', align: 'right', render: scoreText },
    { title: '距目标', dataIndex: 'vs', align: 'right', render: gapText },
  ]

  return (
    <div className="page">
      <Card styles={{ body: { padding: 20 } }}>
        <Text type="secondary">测试能力成熟度月报 · antd</Text>
        <Title level={2} style={{ margin: '4px 0 8px', color: '#173b63' }}>测试能力成熟度月报</Title>
        <Paragraph type="secondary" style={{ marginBottom: 8 }}>
          报告期 {report.period}　·　口径 {report.version}　·　年度目标 <b>{report.target.toFixed(1)}</b>　·　满分 {report.full.toFixed(1)}
          <br />
          看板：{report.items} 项 / {report.teams} 科组 / {report.orgs} 组织　·　可计分 {report.scoredTeams} 科组　·　全中心得分 <b>{report.center.toFixed(2)}</b>（科组等权）
        </Paragraph>
        <Space wrap>
          <Tag color="blue">仅第一大块</Tag>
          <Tag>数字来自看板 V2.0.26 · 不编</Tag>
          <Tag>双击打开 · 不启服务</Tag>
        </Space>
      </Card>

      <Title level={4} style={{ margin: '20px 0 12px', color: '#173b63' }}>一、各业务测试能力成熟度</Title>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Chapter no="1.1" title="全中心：目标、当前得分、距目标差距">
            <Row gutter={16}>
              <Col xs={24} md={8}><Statistic title="年度目标" value={report.target} precision={1} /></Col>
              <Col xs={24} md={8}><Statistic title="当前得分" value={report.center} precision={2} /></Col>
              <Col xs={24} md={8}>
                <Statistic title="距目标差距" value={report.gap} precision={2} valueStyle={{ color: '#a94442' }} />
              </Col>
            </Row>
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">现状 {report.center.toFixed(2)} / 满分 {report.full.toFixed(1)}，红线 = 目标 {report.target.toFixed(1)}</Text>
              <Progress
                percent={(report.center / report.full) * 100}
                strokeColor="#287a8d"
                trailColor="#e4e9ee"
                format={() => report.center.toFixed(2)}
              />
            </div>
            <Paragraph style={{ marginTop: 8 }}>
              可计分 {report.scoredTeams} / {report.teams} 科组。{report.unscoredTeams.join('、')} 无 2/3/4 级可计分项，不进入总分。总分是科组等权，不是条目合并。
            </Paragraph>
            <Title level={5}>分领域现状（可计分科组等权）</Title>
            <div className="chart-box">
              <Bar data={domainData} xField="score" yField="name" {...barCommon} />
            </div>
            <Paragraph type="secondary">满分 4.0。看板本期无「合规」可计分科组，不编。</Paragraph>
          </Chapter>
        </Col>

        <Col span={24}>
          <Chapter no="1.2" title="部门对比：得分、差距、高低">
            <Table
              size="small"
              pagination={false}
              columns={deptCols}
              dataSource={report.depts.map((d, i) => ({ ...d, key: i }))}
            />
            <div className="chart-box" style={{ marginTop: 12, height: 280 }}>
              <Bar data={deptData} xField="score" yField="name" {...barCommon} />
            </div>
          </Chapter>
        </Col>

        <Col span={24}>
          <Chapter no="1.3" title="每个部门下的科组得分和短板">
            <Paragraph type="secondary">短板 = 该科组可计分领域中最低分。无可计分项不编分。</Paragraph>
            {report.depts.map((d) => (
              <div key={d.name} style={{ marginBottom: 20 }}>
                <Title level={5}>
                  {d.name}
                  <Text type="secondary" style={{ marginLeft: 8, fontWeight: 400 }}>
                    部门 {d.score.toFixed(2)}　距目标 {gapText(d.vsTarget)}
                  </Text>
                </Title>
                <Table
                  size="small"
                  pagination={false}
                  columns={teamCols}
                  dataSource={d.teams.map((t, i) => ({ ...t, key: i }))}
                />
              </div>
            ))}
            <Title level={5}>前 5% / 后 5%（可计分 {report.scoredTeams} 科组，约 {report.teamsListed.filter((t) => t.band === '前 5%').length} 个）</Title>
            <Table
              size="small"
              pagination={false}
              columns={rankCols}
              dataSource={report.teamsListed.map((r, i) => ({ ...r, key: i }))}
            />
            <div className="chart-box" style={{ marginTop: 12 }}>
              <Bar data={teamRankData} xField="score" yField="team" {...barCommon} />
            </div>
          </Chapter>
        </Col>

        <Col span={24}>
          <Chapter no="1.4" title="未达成缺口（跟在对应组织下面）">
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="本期 JSON 无计划月份字段，未达成项月份不编。缺口只写得分距 3.0 和领域短板。"
            />
            <Card size="small" className="gap-card" title="全中心">
              <Paragraph>
                距目标 <b>{gapText(report.gap)}</b>。未过线领域：{domainBelow.map((d) => `${d.name} ${d.score.toFixed(2)}`).join('、') || '无'}。
                已过线：{domainAbove.map((d) => `${d.name} ${d.score.toFixed(2)}`).join('、') || '无'}。
              </Paragraph>
            </Card>
            {report.depts.map((d) => (
              <Card size="small" className="gap-card" title={d.name} key={d.name}>
                <Paragraph>
                  部门距目标 <b>{gapText(d.vsTarget)}</b>。
                </Paragraph>
                {d.teams.map((t) => (
                  <Paragraph key={t.team} style={{ marginBottom: 4 }}>
                    {t.team}：{t.score == null ? '无可计分项，不编分。' : `得分 ${t.score.toFixed(2)}，距目标 ${gapText(t.vs)}，短板 ${t.weak}。`}
                  </Paragraph>
                ))}
              </Card>
            ))}
          </Chapter>
        </Col>
      </Row>

      <Paragraph type="secondary" style={{ marginTop: 20 }}>
        数字来自看板 {report.version}，科组等权。缺项不编。本期只出第一大块。
      </Paragraph>
    </div>
  )
}
