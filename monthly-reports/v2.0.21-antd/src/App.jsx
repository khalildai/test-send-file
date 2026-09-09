import { Card, Col, Progress, Row, Table, Tag, Typography } from 'antd'
import { report } from './data.js'

const { Title, Text } = Typography
const DOMS = report.domainOrder

function gapText(v) {
  if (v == null) return '—'
  const n = Number(v)
  return n > 0 ? `+${n.toFixed(2)}` : n.toFixed(2)
}

function scoreText(v) {
  return v == null ? '—' : Number(v).toFixed(2)
}

function barColor(score) {
  if (score == null) return '#c5ced6'
  if (score >= 3) return '#1d7a35'
  if (score < 1.75) return '#a94442'
  return '#173b63'
}

function ScoreBar({ score }) {
  if (score == null) return <span className="muted">—</span>
  const pct = Math.max(0, Math.min(100, (score / report.full) * 100))
  return (
    <div className="barline">
      <div className="track"><i style={{ width: `${pct}%`, background: barColor(score) }} /></div>
      <b className="cell-num">{score.toFixed(2)}</b>
    </div>
  )
}

function domainCols() {
  return DOMS.map((name) => ({
    title: name,
    dataIndex: ['domains', name],
    align: 'right',
    width: 88,
    render: (v) => <span className="cell-num">{scoreText(v)}</span>,
  }))
}

export default function App() {
  const teamRows = report.depts.flatMap((d) =>
    d.teams.map((t, i) => ({
      key: `${d.name}-${t.team}-${i}`,
      dept: d.name,
      ...t,
    })),
  )

  const gapRows = [
    {
      key: 'center',
      org: '全中心',
      score: report.center,
      vs: report.gap,
      note: `未过线领域：${report.domains.map((d) => `${d.name} ${d.score.toFixed(2)}`).join('、')}。合规无计分科组，不编。`,
    },
    ...report.depts.map((d) => ({
      key: `d-${d.name}`,
      org: d.name,
      score: d.score,
      vs: d.vsTarget,
      note: d.teams
        .filter((t) => t.score == null || t.vs < 0)
        .map((t) => (t.score == null ? `${t.team} 无可计分` : `${t.team} ${t.score.toFixed(2)} / ${t.weak}`))
        .join('；') || '—',
    })),
  ]

  return (
    <div className="page">
      <Card size="small">
        <Title level={4} style={{ margin: 0, color: '#173b63' }}>测试能力成熟度月报 · {report.period}</Title>
        <Text type="secondary">
          {report.version}　目标 {report.target.toFixed(1)}　满分 {report.full.toFixed(1)}　
          {report.items} 项 / {report.teams} 科组（可计分 {report.scoredTeams}）/ {report.orgs} 组织　
          科组等权　缺项不编
        </Text>
      </Card>

      <Title level={5} style={{ margin: '8px 0 8px', color: '#173b63' }}>一、各业务测试能力成熟度</Title>

      <Card size="small" title={<span><Text style={{ color: '#287a8d', fontWeight: 700 }}>1.1 </Text>全中心：目标、当前得分、距目标差距</span>}>
        <Row gutter={12}>
          <Col span={8}><Text type="secondary">目标</Text><div style={{ fontSize: 22, fontWeight: 700 }}>{report.target.toFixed(1)}</div></Col>
          <Col span={8}><Text type="secondary">当前得分</Text><div style={{ fontSize: 22, fontWeight: 700 }}>{report.center.toFixed(2)}</div></Col>
          <Col span={8}><Text type="secondary">距目标</Text><div style={{ fontSize: 22, fontWeight: 700, color: '#a94442' }}>{gapText(report.gap)}</div></Col>
        </Row>
        <Progress percent={(report.center / report.full) * 100} strokeColor="#287a8d" trailColor="#e4e9ee" format={() => report.center.toFixed(2)} style={{ margin: '8px 0' }} />
        <Text type="secondary">可计分 {report.scoredTeams}/{report.teams}。{report.unscoredTeams.join('、')} 无 2/3/4 级可计分，不进总分。</Text>
        <div style={{ marginTop: 8, fontWeight: 600 }}>领域得分</div>
        <Table
          size="small"
          pagination={false}
          rowKey="name"
          columns={[
            { title: '领域', dataIndex: 'name', width: 140 },
            { title: '得分', dataIndex: 'score', render: (v) => <ScoreBar score={v} /> },
            { title: '距目标', dataIndex: 'score', width: 90, align: 'right', render: (v) => gapText(v - report.target) },
          ]}
          dataSource={report.domains}
        />
      </Card>

      <Card size="small" title={<span><Text style={{ color: '#287a8d', fontWeight: 700 }}>1.2 </Text>部门对比：得分、差距、高低、领域</span>}>
        <Table
          size="small"
          pagination={false}
          rowKey="name"
          scroll={{ x: 980 }}
          columns={[
            { title: '部门', dataIndex: 'name', width: 170, fixed: 'left' },
            { title: '得分', dataIndex: 'score', width: 130, render: (v) => <ScoreBar score={v} /> },
            { title: '相对中心', dataIndex: 'vsCenter', width: 88, align: 'right', render: gapText },
            {
              title: '高低',
              dataIndex: 'vsCenter',
              width: 88,
              render: (v) => (v > 0 ? <Tag color="success">高</Tag> : <Tag color="error">低</Tag>),
            },
            { title: '距目标', dataIndex: 'vsTarget', width: 80, align: 'right', render: gapText },
            { title: '计分', dataIndex: 'scoredTeams', width: 70, render: (_, r) => `${r.scoredTeams}/${r.teamCount}` },
            ...domainCols(),
          ]}
          dataSource={report.depts}
        />
      </Card>

      <Card size="small" title={<span><Text style={{ color: '#287a8d', fontWeight: 700 }}>1.3 </Text>科组得分、短板、领域</span>}>
        <Table
          size="small"
          pagination={false}
          rowKey="key"
          scroll={{ x: 1100 }}
          columns={[
            { title: '部门', dataIndex: 'dept', width: 160 },
            { title: '科组', dataIndex: 'team', width: 180 },
            { title: '得分', dataIndex: 'score', width: 130, render: (v) => <ScoreBar score={v} /> },
            { title: '距目标', dataIndex: 'vs', width: 80, align: 'right', render: gapText },
            { title: '短板', dataIndex: 'weak', width: 140 },
            ...domainCols(),
          ]}
          dataSource={teamRows}
        />
      </Card>

      <Card size="small" title={<span><Text style={{ color: '#287a8d', fontWeight: 700 }}>1.4 </Text>未达成缺口（跟组织）</span>}>
        <Text type="secondary">无计划月份字段，月份不编。缺口=距 3.0 + 领域短板。</Text>
        <Table
          size="small"
          pagination={false}
          rowKey="key"
          columns={[
            { title: '组织', dataIndex: 'org', width: 180 },
            { title: '得分', dataIndex: 'score', width: 80, align: 'right', render: scoreText },
            { title: '距目标', dataIndex: 'vs', width: 80, align: 'right', render: gapText },
            { title: '缺口', dataIndex: 'note' },
          ]}
          dataSource={gapRows}
        />
      </Card>
    </div>
  )
}
