import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Alert, Button, Card, Col, Divider, Modal, Progress, Row, Select, Space, Statistic, Table, Tag, Typography } from 'antd';
import 'antd/dist/reset.css';
import './styles.css';

const { Title, Text } = Typography;

const products = [
  { name: '智慧城市平台 V3.0', market: 29, defects: 347, reopen: 7.2, leaks: 2, trend: [19, 22, 24, 25, 28, 29] },
  { name: '5G 基站主控板 V1.0', market: 22, defects: 231, reopen: 6.3, leaks: 1, trend: [17, 18, 21, 19, 22, 22] },
  { name: '智能支付平台 V2.0', market: 18, defects: 286, reopen: 4.8, leaks: 1, trend: [14, 16, 15, 17, 18, 18] },
  { name: '边缘计算网关 R2.0', market: 14, defects: 198, reopen: 4.2, leaks: 0, trend: [16, 15, 14, 13, 14, 14] },
  { name: '移动办公 App R1.3', market: 11, defects: 154, reopen: 3.1, leaks: 1, trend: [12, 11, 13, 12, 11, 11] },
];

const trendLabels = ['4月', '5月', '6月', '7月', '8月', '9月'];

function Trend({ values, color = '#0f62fe', unit = '个' }) {
  const max = Math.max(...values, 1);
  return <div className="trend" aria-label={`近六期趋势，单位${unit}`}>
    {values.map((value, index) => <div className="trend-column" key={`${value}-${index}`}><i style={{ height: `${Math.max(12, value / max * 100)}%`, background: color }} /><span>{trendLabels[index]}</span></div>)}
  </div>;
}

function MetricCard({ title, value, suffix, note, values, onClick }) {
  return <Card className="metric-card" size="small" onClick={onClick} hoverable={Boolean(onClick)}>
    <Text type="secondary">{title}</Text>
    <Statistic value={value} suffix={suffix} valueStyle={{ color: '#161616', fontSize: 30, fontWeight: 400 }} />
    <Text className="metric-note">{note}</Text>
    {values && <Trend values={values} />}
  </Card>;
}

function App() {
  const [product, setProduct] = useState('全部产品');
  const [detail, setDetail] = useState(null);
  const selected = useMemo(() => product === '全部产品' ? products : products.filter(item => item.name === product), [product]);
  const totals = useMemo(() => ({
    market: selected.reduce((sum, item) => sum + item.market, 0),
    defects: selected.reduce((sum, item) => sum + item.defects, 0),
    reopen: selected.length ? selected.reduce((sum, item) => sum + item.reopen, 0) / selected.length : 0,
    leaks: selected.reduce((sum, item) => sum + item.leaks, 0),
  }), [selected]);
  const marketTrend = [82, 86, 89, 96, 102, totals.market];
  const defectTrend = [804, 846, 902, 1018, 1129, totals.defects];
  const reopenTrend = [6.4, 6.1, 6.0, 5.8, 5.6, totals.reopen];
  const leakTrend = [10, 9, 9, 8, 7, totals.leaks];
  const tableRows = selected.map((item, index) => ({ key: item.name, ...item, status: index === 0 ? '需关注' : '观察中' }));

  const showDetail = (title, rows = tableRows) => setDetail({ title, rows });
  const columns = [
    { title: '产品', dataIndex: 'name', key: 'name' },
    { title: '市场问题', dataIndex: 'market', key: 'market', render: value => `${value} 个` },
    { title: '缺陷数量', dataIndex: 'defects', key: 'defects', render: value => `${value} 个` },
    { title: 'Reopen 率', dataIndex: 'reopen', key: 'reopen', render: value => `${value.toFixed(1)}%` },
    { title: '漏测数', dataIndex: 'leaks', key: 'leaks', render: value => `${value} 个` },
    { title: '状态', dataIndex: 'status', key: 'status', render: value => <Tag color={value === '需关注' ? 'error' : 'processing'}>{value}</Tag> },
  ];

  return <div className="app-shell">
    <header className="topbar"><div><Text className="eyebrow">QUALITY MANAGEMENT / PRODUCT HEALTH</Text><Title level={2}>测试管理者驾驶舱</Title><Text type="secondary">用一屏看懂当前产品开发与设计质量</Text></div><Space><Tag color="blue">临时演示数据</Tag><Select value={product} onChange={setProduct} options={[{ value: '全部产品', label: '全部产品' }, ...products.map(item => ({ value: item.name, label: item.name }))]} /></Space></header>
    <main className="content">
      <Alert className="demo-alert" type="info" showIcon message="当前为结构验证版本" description="指标口径、趋势和产品分布均使用临时演示数据；点击指标卡可查看产品级明细，正式接入后保留同一管理视图。" />
      <section className="conclusion"><div><Text type="secondary">当前质量结论</Text><Title level={3}>质量信号总体可控，但高风险产品的缺陷与市场反馈仍在上升。</Title></div><div className="conclusion-items"><div><Text type="secondary">做得好的</Text><b>漏测数较前期下降，问题已能在项目层面聚合跟踪。</b></div><div><Text type="secondary">需要关注的</Text><b>市场问题与缺陷存量集中在智慧城市平台和主控板产品。</b></div></div></section>

      <section><div className="section-heading"><div><Title level={3}>业务质量关键指标</Title><Text type="secondary">市场反馈与项目质量的规模、趋势和结构分布</Text></div><Button type="link" onClick={() => showDetail('业务质量明细')}>查看明细</Button></div>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}><Card title="市场问题" extra={<Tag color="gold">市场反馈</Tag>}><Row gutter={[12, 12]}><Col span={12}><MetricCard title="市场问题数" value={totals.market} suffix="个" note="较前期 +6.2%" values={marketTrend} onClick={() => showDetail('市场问题明细')} /></Col><Col span={12}><MetricCard title="近六期趋势" value={marketTrend.at(-1)} suffix="个" note="持续观察反馈变化" values={marketTrend} /></Col></Row><Divider /><Text strong>所属产品分布</Text>{selected.map(item => <div className="product-bar" key={item.name}><div><span>{item.name}</span><b>{item.market} 个</b></div><Progress percent={Math.round(item.market / Math.max(...selected.map(row => row.market), 1) * 100)} showInfo={false} strokeColor="#0f62fe" trailColor="#e0e0e0" /></div>)}</Card></Col>
          <Col xs={24} md={12}><Card title="项目测试质量" extra={<Tag color="blue">项目视图</Tag>}><Row gutter={[12, 12]}><Col span={8}><MetricCard title="缺陷数量" value={totals.defects} suffix="个" note="较前期 +4.8%" values={defectTrend} onClick={() => showDetail('项目缺陷明细')} /></Col><Col span={8}><MetricCard title="Reopen 率" value={totals.reopen} precision={1} suffix="%" note="较前期 -0.6 个百分点" values={reopenTrend} onClick={() => showDetail('Reopen 明细')} /></Col><Col span={8}><MetricCard title="漏测数" value={totals.leaks} suffix="个" note="较前期 -2.1%" values={leakTrend} onClick={() => showDetail('漏测明细')} /></Col></Row><Divider /><Text type="secondary">趋势说明</Text><p className="explain">缺陷数量反映当前项目质量压力；Reopen 率反映返工稳定性；漏测数反映问题是否在发布后才暴露。</p></Card></Col>
        </Row>
      </section>

      <section><div className="section-heading"><div><Title level={3}>产品质量对比</Title><Text type="secondary">按产品查看当前质量信号，归属、问题单和执行细节通过下穿查看</Text></div><Button onClick={() => showDetail('产品质量对比')}>下穿查看</Button></div><Card bodyStyle={{ padding: 0 }}><Table columns={columns} dataSource={tableRows} pagination={false} scroll={{ x: 760 }} /></Card></section>
    </main>
    <Modal open={Boolean(detail)} title={detail?.title} onCancel={() => setDetail(null)} footer={<Button type="primary" onClick={() => setDetail(null)}>关闭</Button>} width={760}><Table columns={columns} dataSource={detail?.rows || []} pagination={false} size="small" /></Modal>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
