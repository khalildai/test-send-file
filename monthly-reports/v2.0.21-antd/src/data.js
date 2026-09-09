/** 数字来自 V2.0.26 看板。科组等权。领域=该组织可计分科组在该领域等权。缺项不编。 */
export const report = {
  "period": "2026-09",
  "version": "V2.0.26 口径",
  "target": 3.0,
  "full": 4.0,
  "center": 0.96,
  "gap": -2.04,
  "items": 1883,
  "teams": 36,
  "orgs": 10,
  "scoredTeams": 32,
  "unscoredTeams": [
    "电柜测试及系统架构能力组",
    "安规测试组",
    "工业机器人软件测试组",
    "工业机器人整机产品测试组"
  ],
  "domainOrder": [
    "环境可靠性",
    "硬件",
    "软件",
    "EMC",
    "机械"
  ],
  "domains": [
    {
      "name": "环境可靠性",
      "score": 1.45
    },
    {
      "name": "硬件",
      "score": 1.13
    },
    {
      "name": "软件",
      "score": 0.9
    },
    {
      "name": "EMC",
      "score": 0.67
    },
    {
      "name": "机械",
      "score": 0.61
    }
  ],
  "depts": [
    {
      "name": "产品合规与准入部",
      "score": 1.45,
      "vsCenter": 0.49,
      "vsTarget": -1.55,
      "scoredTeams": 1,
      "teamCount": 2,
      "domains": {
        "环境可靠性": 1.45
      },
      "teams": [
        {
          "team": "环境可靠性测试组",
          "score": 1.45,
          "vs": -1.55,
          "domains": {
            "环境可靠性": 1.45
          },
          "weak": "环境可靠性 1.45"
        },
        {
          "team": "安规测试组",
          "score": null,
          "vs": null,
          "domains": {},
          "weak": "无可计分项"
        }
      ]
    },
    {
      "name": "驱动产品测试部",
      "score": 1.11,
      "vsCenter": 0.15,
      "vsTarget": -1.89,
      "scoredTeams": 5,
      "teamCount": 5,
      "domains": {
        "硬件": 1.12,
        "软件": 1.08
      },
      "teams": [
        {
          "team": "运控系统测试组",
          "score": 1.27,
          "vs": -1.73,
          "domains": {
            "软件": 1.27
          },
          "weak": "软件 1.27"
        },
        {
          "team": "变频驱动测试组",
          "score": 1.22,
          "vs": -1.78,
          "domains": {
            "软件": 1.25,
            "硬件": 1.19
          },
          "weak": "硬件 1.19"
        },
        {
          "team": "大型传动测试组",
          "score": 1.09,
          "vs": -1.91,
          "domains": {
            "软件": 0.98,
            "硬件": 1.19
          },
          "weak": "软件 0.98"
        },
        {
          "team": "CNC测试组",
          "score": 1.06,
          "vs": -1.94,
          "domains": {
            "软件": 1.06
          },
          "weak": "软件 1.06"
        },
        {
          "team": "传感器测试组",
          "score": 0.92,
          "vs": -2.08,
          "domains": {
            "软件": 0.84,
            "硬件": 0.99
          },
          "weak": "软件 0.84"
        }
      ]
    },
    {
      "name": "能源产品测试部",
      "score": 1.09,
      "vsCenter": 0.13,
      "vsTarget": -1.91,
      "scoredTeams": 4,
      "teamCount": 4,
      "domains": {
        "硬件": 1.15,
        "软件": 1.06
      },
      "teams": [
        {
          "team": "工商及户储测试组",
          "score": 1.18,
          "vs": -1.82,
          "domains": {
            "软件": 1.12,
            "硬件": 1.23
          },
          "weak": "软件 1.12"
        },
        {
          "team": "大储测试组",
          "score": 1.12,
          "vs": -1.88,
          "domains": {
            "软件": 1.02,
            "硬件": 1.21
          },
          "weak": "软件 1.02"
        },
        {
          "team": "组串测试组",
          "score": 1.1,
          "vs": -1.9,
          "domains": {
            "软件": 1.02,
            "硬件": 1.18
          },
          "weak": "软件 1.02"
        },
        {
          "team": "并网标准与硬件测试组",
          "score": 0.96,
          "vs": -2.04,
          "domains": {
            "硬件": 0.96
          },
          "weak": "硬件 0.96"
        }
      ]
    },
    {
      "name": "硬件与EMC测试部",
      "score": 1.08,
      "vsCenter": 0.12,
      "vsTarget": -1.92,
      "scoredTeams": 5,
      "teamCount": 5,
      "domains": {
        "硬件": 1.18,
        "EMC": 0.67
      },
      "teams": [
        {
          "team": "控制硬件测试组",
          "score": 1.2,
          "vs": -1.8,
          "domains": {
            "硬件": 1.2
          },
          "weak": "硬件 1.20"
        },
        {
          "team": "伺服硬件测试",
          "score": 1.17,
          "vs": -1.83,
          "domains": {
            "硬件": 1.17
          },
          "weak": "硬件 1.17"
        },
        {
          "team": "智能机器人硬件测试组",
          "score": 1.17,
          "vs": -1.83,
          "domains": {
            "硬件": 1.17
          },
          "weak": "硬件 1.17"
        },
        {
          "team": "变频硬件测试组",
          "score": 1.17,
          "vs": -1.83,
          "domains": {
            "硬件": 1.17
          },
          "weak": "硬件 1.17"
        },
        {
          "team": "EMC测试组",
          "score": 0.67,
          "vs": -2.33,
          "domains": {
            "EMC": 0.67
          },
          "weak": "EMC 0.67"
        }
      ]
    },
    {
      "name": "电梯产品测试部",
      "score": 1.05,
      "vsCenter": 0.09,
      "vsTarget": -1.95,
      "scoredTeams": 2,
      "teamCount": 2,
      "domains": {
        "硬件": 1.19,
        "软件": 0.92
      },
      "teams": [
        {
          "team": "电梯电气测试组",
          "score": 1.07,
          "vs": -1.93,
          "domains": {
            "软件": 1.0,
            "硬件": 1.13
          },
          "weak": "软件 1.00"
        },
        {
          "team": "电梯控制测试组",
          "score": 1.04,
          "vs": -1.96,
          "domains": {
            "硬件": 1.24,
            "软件": 0.84
          },
          "weak": "软件 0.84"
        }
      ]
    },
    {
      "name": "α实验室与控制测试部",
      "score": 0.93,
      "vsCenter": -0.03,
      "vsTarget": -2.07,
      "scoredTeams": 8,
      "teamCount": 8,
      "domains": {
        "软件": 0.93
      },
      "teams": [
        {
          "team": "中小PLC产品测试组",
          "score": 1.25,
          "vs": -1.75,
          "domains": {
            "软件": 1.25
          },
          "weak": "软件 1.25"
        },
        {
          "team": "通信系统测试组（网络产品）",
          "score": 1.21,
          "vs": -1.79,
          "domains": {
            "软件": 1.21
          },
          "weak": "软件 1.21"
        },
        {
          "team": "OS测试组",
          "score": 1.0,
          "vs": -2.0,
          "domains": {
            "软件": 1.0
          },
          "weak": "软件 1.00"
        },
        {
          "team": "中大PLC产品测试组",
          "score": 0.83,
          "vs": -2.17,
          "domains": {
            "软件": 0.83
          },
          "weak": "软件 0.83"
        },
        {
          "team": "通信系统测试组（网络平台）",
          "score": 0.83,
          "vs": -2.17,
          "domains": {
            "软件": 0.83
          },
          "weak": "软件 0.83"
        },
        {
          "team": "iFA软件测试组",
          "score": 0.83,
          "vs": -2.17,
          "domains": {
            "软件": 0.83
          },
          "weak": "软件 0.83"
        },
        {
          "team": "HMI&PAC产品测试组",
          "score": 0.74,
          "vs": -2.26,
          "domains": {
            "软件": 0.74
          },
          "weak": "软件 0.74"
        },
        {
          "team": "IO产品测试组",
          "score": 0.74,
          "vs": -2.26,
          "domains": {
            "软件": 0.74
          },
          "weak": "软件 0.74"
        }
      ]
    },
    {
      "name": "智能机器人产品测试部",
      "score": 0.75,
      "vsCenter": -0.21,
      "vsTarget": -2.25,
      "scoredTeams": 2,
      "teamCount": 5,
      "domains": {
        "软件": 0.75
      },
      "teams": [
        {
          "team": "视觉解决方案及产品测试组",
          "score": 1.03,
          "vs": -1.97,
          "domains": {
            "软件": 1.03
          },
          "weak": "软件 1.03"
        },
        {
          "team": "人形机器人产品测试组",
          "score": 0.47,
          "vs": -2.53,
          "domains": {
            "软件": 0.47
          },
          "weak": "软件 0.47"
        },
        {
          "team": "电柜测试及系统架构能力组",
          "score": null,
          "vs": null,
          "domains": {},
          "weak": "无可计分项"
        },
        {
          "team": "工业机器人软件测试组",
          "score": null,
          "vs": null,
          "domains": {},
          "weak": "无可计分项"
        },
        {
          "team": "工业机器人整机产品测试组",
          "score": null,
          "vs": null,
          "domains": {},
          "weak": "无可计分项"
        }
      ]
    },
    {
      "name": "机电传动产品测试部",
      "score": 0.6,
      "vsCenter": -0.36,
      "vsTarget": -2.4,
      "scoredTeams": 5,
      "teamCount": 5,
      "domains": {
        "硬件": 0.94,
        "软件": 0.42,
        "机械": 0.61
      },
      "teams": [
        {
          "team": "传动解决方案测试组",
          "score": 0.76,
          "vs": -2.24,
          "domains": {
            "软件": 0.68,
            "硬件": 1.05,
            "机械": 0.56
          },
          "weak": "机械 0.56"
        },
        {
          "team": "电机测试组",
          "score": 0.67,
          "vs": -2.33,
          "domains": {
            "机械": 0.67
          },
          "weak": "机械 0.67"
        },
        {
          "team": "工业电源测试组",
          "score": 0.54,
          "vs": -2.46,
          "domains": {
            "硬件": 0.83,
            "软件": 0.24
          },
          "weak": "软件 0.24"
        },
        {
          "team": "减速机测试组测试组",
          "score": 0.53,
          "vs": -2.47,
          "domains": {
            "机械": 0.53
          },
          "weak": "机械 0.53"
        },
        {
          "team": "高速流体测试组",
          "score": 0.51,
          "vs": -2.49,
          "domains": {
            "软件": 0.35,
            "机械": 0.66
          },
          "weak": "软件 0.35"
        }
      ]
    }
  ]
}
