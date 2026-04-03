import { motion } from 'motion/react';
import { useMemo } from 'react';

// 神经流背景层：
// - nodes：漂浮光点
// - paths：流动路径（纤维）
// 通过随机参数提升“有机感”，并使用 useMemo 保证一次挂载内视觉稳定。
export function NeuralFlowBackground() {
  // 画布参数与节点数量。这里保持固定值，便于控制性能和视觉密度。
  const nodeCount = 40;
  const width = 1000;
  const height = 1000;

  // 随机生成节点，用于构建背景“星点/神经元”层。
  const nodes = useMemo(() => {
    return [...Array(nodeCount)].map((_, i) => ({
      id: i,
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 3 + 1,
      color: Math.random() > 0.5 ? '#06b6d4' : '#ffffff',
      delay: Math.random() * 5,
      speed: Math.random() * 2 + 1,
    }));
  }, []);

  // 随机生成曲线路径，模拟“神经网络流动”。
  // 关键点：每段角度只做小范围扰动，避免折线感太重。
  const paths = useMemo(() => {
    return [...Array(18)].map((_, i) => {
      const startX = Math.random() * width;
      const startY = Math.random() * height;
      const angle = Math.random() * Math.PI * 2;
      const points = [{ x: startX, y: startY }];

      // 逐段推进路径点，构建一条连续光纤。
      for (let j = 1; j < 6; j += 1) {
        const prev = points[j - 1];
        const dist = 150 + Math.random() * 100;
        const currentAngle = angle + (Math.random() - 0.5) * 1.0;
        points.push({
          x: prev.x + Math.cos(currentAngle) * dist,
          y: prev.y + Math.sin(currentAngle) * dist,
        });
      }

      let d = `M ${points[0].x} ${points[0].y}`;
      // 使用二次贝塞尔做平滑过渡，避免尖锐折角。
      for (let j = 1; j < points.length - 1; j += 1) {
        const xc = (points[j].x + points[j + 1].x) / 2;
        const yc = (points[j].y + points[j + 1].y) / 2;
        d += ` Q ${points[j].x} ${points[j].y} ${xc} ${yc}`;
      }
      d += ` L ${points[points.length - 1].x} ${points[points.length - 1].y}`;

      return {
        id: i,
        d,
        color: Math.random() > 0.6 ? '#ec4899' : '#3b82f6',
        delay: Math.random() * 5,
        duration: Math.random() * 6 + 6,
      };
    });
  }, []);

  return (
    <div className="absolute inset-0 opacity-70 pointer-events-none overflow-hidden">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="xMidYMid slice">
        {/* 双层路径：一层慢速底光 + 一层线性脉冲，形成“流动感” */}
        {paths.map((path) => (
          <g key={path.id}>
            <motion.path
              d={path.d}
              fill="none"
              stroke={path.color}
              strokeWidth="0.4"
              strokeLinecap="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: [0, 1, 1, 0],
                opacity: [0, 0.15, 0.15, 0],
              }}
              transition={{
                duration: path.duration * 1.5,
                repeat: Infinity,
                ease: 'easeInOut',
                delay: path.delay,
              }}
              className="blur-[0.5px]"
            />
            <motion.path
              d={path.d}
              fill="none"
              stroke={path.color}
              strokeWidth="0.8"
              strokeLinecap="round"
              initial={{ pathLength: 0.1, pathOffset: 0, opacity: 0 }}
              animate={{
                pathOffset: [0, 1],
                opacity: [0, 0.8, 0],
              }}
              transition={{
                duration: path.duration,
                repeat: Infinity,
                ease: 'linear',
                delay: path.delay,
              }}
              className="blur-[1px]"
              style={{
                filter: `drop-shadow(0 0 3px ${path.color})`,
              }}
            />
          </g>
        ))}

        {/* 节点双层：外圈柔光 + 内芯亮点 */}
        {nodes.map((node) => {
          const progress = node.y / height;
          const distFromMiddle = Math.abs(progress - 0.5) * 2;
          const baseOpacity = 0.05 + Math.pow(distFromMiddle, 2) * 0.7;

          return (
            <g key={node.id}>
              <motion.circle
                cx={node.x}
                cy={node.y}
                r={node.size * 2}
                fill={node.color}
                initial={{ opacity: 0 }}
                animate={{
                  opacity: [baseOpacity * 0.5, baseOpacity, baseOpacity * 0.5],
                  scale: [1, 1.5, 1],
                  x: [0, (Math.random() - 0.5) * 50, 0],
                  y: [0, (Math.random() - 0.5) * 50, 0],
                }}
                transition={{
                  duration: 10 + node.speed,
                  repeat: Infinity,
                  ease: 'easeInOut',
                  delay: node.delay,
                }}
                className="blur-[2px]"
              />
              <motion.circle
                cx={node.x}
                cy={node.y}
                r={node.size}
                fill="#ffffff"
                initial={{ opacity: 0 }}
                animate={{
                  opacity: [baseOpacity, baseOpacity * 1.5, baseOpacity],
                  scale: [1, 1.2, 1],
                }}
                transition={{
                  duration: 5,
                  repeat: Infinity,
                  ease: 'easeInOut',
                  delay: node.delay,
                }}
              />
            </g>
          );
        })}

        {/* 对角扫描线：提供额外动势，避免画面静止 */}
        {[...Array(8)].map((_, i) => (
          <motion.line
            key={i}
            x1="-10%"
            y1={i * 15 + '%'}
            x2="110%"
            y2={i * 15 + 20 + '%'}
            stroke={i % 2 === 0 ? '#ec4899' : '#06b6d4'}
            strokeWidth="0.5"
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0, 0.1, 0],
              strokeDashoffset: [200, 0],
            }}
            strokeDasharray="100 200"
            transition={{
              duration: 15 + i,
              repeat: Infinity,
              ease: 'linear',
              delay: i * 2,
            }}
          />
        ))}
      </svg>
    </div>
  );
}
