# 补充方案05：WebRTC远程会诊技术方案

> 解决问题：P2 v3.0远程视频会诊功能缺少技术方案
> 优先级：P3（Q3前完成方案，Q4实施）
> 版本：P2 v3.0（12月）

---

## 一、需求概述

| 维度 | 要求 |
|------|------|
| **场景** | MDT多学科会诊、远程专家问诊、跨院区协作 |
| **参与人数** | ≥5人同时在线 |
| **音视频延迟** | ≤500ms |
| **功能** | 视频通话 + 屏幕共享 + 文字聊天 + 文件共享 + 录制 |
| **合规** | 会诊记录完整保留、参会人签名确认、患者数据不出境 |
| **浏览器** | Chrome 90+（已有浏览器要求） |

---

## 二、技术选型

### 2.1 方案对比

| 方案 | 架构 | 开源 | 部署方式 | 适用规模 | 延迟 | 录制 |
|------|------|------|---------|---------|------|------|
| **LiveKit** | SFU | ✅ Apache 2.0 | 自部署/云 | 100+参与者 | <100ms | ✅ 内置 |
| mediasoup | SFU | ✅ ISC | 自部署 | 数十人 | <100ms | ❌ 需扩展 |
| Jitsi Meet | SFU | ✅ Apache 2.0 | 自部署/云 | 75+参与者 | <200ms | ✅ Jibri |
| 阿里云RTC | SFU/MCU | ❌ 付费 | 云服务 | 无限 | <200ms | ✅ |

### 2.2 推荐方案：LiveKit

**选型理由**：
1. **开源 Apache 2.0**：可自部署，数据不出境，满足医疗合规
2. **Go语言实现**：高性能，单节点支持100+参与者
3. **内置录制**：Egress服务支持房间录制和文件导出
4. **SDK完善**：React SDK（`@livekit/components-react`）可直接集成
5. **TURN内置**：无需额外部署TURN/STUN服务器
6. **端到端加密**：支持E2EE，满足医疗数据安全要求

---

## 三、架构设计

### 3.1 部署架构

```
┌─────────────────────────────────────────────────────┐
│                    P2 前端（React 18）                │
│    ┌────────────────────────────────────────────┐    │
│    │  @livekit/components-react                  │    │
│    │  VideoConference / ParticipantTile          │    │
│    │  Chat / ScreenShare / MediaDeviceSelect     │    │
│    └─────────────────────┬──────────────────────┘    │
│                          │ WebSocket + WebRTC         │
└──────────────────────────┼───────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────┐
│                  LiveKit Server                       │
│    ┌──────────────┐  ┌──────────────┐                │
│    │  SFU Router   │  │  TURN Server  │               │
│    │  (选择性转发)  │  │  (NAT穿透)    │               │
│    └──────────────┘  └──────────────┘                │
│    ┌──────────────┐  ┌──────────────┐                │
│    │  Room Manager │  │  Signal Server│               │
│    │  (房间管理)    │  │  (WebSocket)  │               │
│    └──────────────┘  └──────────────┘                │
├──────────────────────────────────────────────────────┤
│                  LiveKit Egress                       │
│    ┌──────────────┐  ┌──────────────┐                │
│    │  Room Composite│ │  Track Egress │               │
│    │  (房间录制)    │  │  (单轨导出)   │               │
│    └───────┬──────┘  └───────┬──────┘                │
│            └────────┬────────┘                        │
│                     ▼                                 │
│              MinIO/OSS 存储                           │
└──────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────┐
│              P2 后端（Spring Boot）                    │
│    ┌──────────────┐  ┌──────────────┐                │
│    │ ConsultService│  │ RecordService │               │
│    │ (会诊管理)    │  │ (录制管理)     │               │
│    │ - 创建会诊    │  │ - 启停录制     │               │
│    │ - Token生成   │  │ - 文件归档     │               │
│    │ - 权限控制    │  │ - 签名确认     │               │
│    └──────────────┘  └──────────────┘                │
└──────────────────────────────────────────────────────┘
```

### 3.2 核心流程

```
1. 医生发起会诊
   → 后端创建会诊记录 + LiveKit Room
   → 生成参与者Token（含权限：发布/订阅/录制）
   → 通知相关医生（WebSocket推送 + 企微消息）

2. 参与者加入
   → 前端用Token连接LiveKit Room
   → 自动协商媒体（视频720p/音频Opus）
   → SFU路由媒体流（选择性转发，带宽自适应）

3. 会诊过程
   → 视频通话 + 屏幕共享（病历/影像/检验报告）
   → 文字聊天（关键讨论记录）
   → 自动录制（Egress服务 → MinIO存储）

4. 会诊结束
   → 停止录制 → 生成录制文件（MP4/MKV）
   → 自动整理会诊摘要（调用P8 AI → 摘要生成）
   → 参会人电子签名确认
   → 归档至患者病历附件
```

---

## 四、前端集成

### 4.1 React组件设计

```typescript
// 会诊视频组件
import {
  LiveKitRoom,
  VideoConference,
  ControlBar,
  Chat,
  ParticipantTile,
  useTracks,
} from '@livekit/components-react';

function ConsultationRoom({ token, serverUrl, consultationId }) {
  return (
    <LiveKitRoom
      serverUrl={serverUrl}
      token={token}
      connect={true}
      audio={true}
      video={true}
    >
      {/* 主视频区域 */}
      <VideoConference />

      {/* 控制栏：静音/摄像头/屏幕共享/录制/退出 */}
      <ControlBar
        controls={{
          microphone: true,
          camera: true,
          screenShare: true,
          leave: true,
          chat: true,
        }}
      />

      {/* 文字聊天 */}
      <Chat />

      {/* 会诊信息侧边栏 */}
      <ConsultationSidebar consultationId={consultationId} />
    </LiveKitRoom>
  );
}
```

### 4.2 屏幕共享增强（医学影像）

```typescript
// 支持共享特定窗口（PACS影像查看器/检验报告）
async function shareScreen() {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: {
      width: { ideal: 1920 },
      height: { ideal: 1080 },
      frameRate: { ideal: 15, max: 30 },
    },
    audio: false,
    // Chrome 107+ 支持系统音频
    systemAudio: 'exclude',
  });
  return stream;
}
```

---

## 五、服务端部署

### 5.1 LiveKit Server配置

```yaml
# livekit.yaml
port: 7880
rtc:
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
  # TURN配置（内置）
  turn:
    enabled: true
    udp_port: 3478
    tls_port: 5349

room:
  max_participants: 20  # 单房间最大参与者
  empty_timeout: 300    # 空房间5分钟自动关闭

# 录制配置
egress:
  enable: true
  s3:
    access_key: ${MINIO_ACCESS_KEY}
    secret: ${MINIO_SECRET_KEY}
    region: cn-hangzhou
    endpoint: http://minio:9000
    bucket: consultation-recordings

# 安全
keys:
  api_key: ${LIVEKIT_API_KEY}
  api_secret: ${LIVEKIT_API_SECRET}

logging:
  level: info
```

### 5.2 资源估算

| 组件 | CPU | 内存 | 存储 | 带宽 |
|------|-----|------|------|------|
| LiveKit Server | 4核 | 8GB | 10GB | 100Mbps |
| LiveKit Egress | 4核 | 8GB | 50GB（临时） | - |
| MinIO（录制存储） | 2核 | 4GB | 500GB/年 | - |
| **合计** | 10核 | 20GB | ~560GB | 100Mbps |

按5人会诊、720p视频估算：
- 每路视频上行：~1.5Mbps
- SFU转发：5人×4路下行×1.5Mbps = 30Mbps
- 录制：~200MB/小时/房间
- 年存储：按每天2次会诊×1小时 = ~150GB/年

---

## 六、医疗合规要求

| 合规项 | 技术实现 |
|--------|---------|
| 会诊记录完整保留 | Egress自动录制→MinIO归档→链接至患者病历 |
| 参会人签名确认 | 会诊结束后弹出签名确认页，电子签名存储 |
| 患者数据不出境 | LiveKit自部署在内网/阿里云国内Region |
| 端到端加密 | LiveKit E2EE（可选开启） |
| 审计追溯 | 会诊创建/加入/离开/录制全链路日志 |
| 患者知情同意 | 会诊前需患者签署远程诊疗同意书 |

---

## 七、版本规划

| Sprint | 内容 | 交付 |
|--------|------|------|
| S1（Q3-W1/W2） | LiveKit部署+基础视频通话 | 2人视频通话POC |
| S2（Q3-W3/W4） | 多人会诊+屏幕共享 | 5人会诊演示 |
| S3（Q4-W1/W2） | 录制+归档+AI摘要 | 完整录制+自动摘要 |
| S4（Q4-W3/W4） | 电子签名+合规审计+集成测试 | 合规验收 |

---

## 八、执行检查清单

- [ ] LiveKit Server Docker镜像准备
- [ ] MinIO存储桶创建（consultation-recordings）
- [ ] LiveKit React SDK安装（@livekit/components-react）
- [ ] Token生成服务开发（Spring Boot + livekit-server-sdk-java）
- [ ] 会诊管理CRUD API开发
- [ ] 前端会诊UI组件开发
- [ ] Egress录制配置与测试
- [ ] 电子签名组件开发
- [ ] 合规审计日志集成
- [ ] 网络带宽压力测试（5人720p）
