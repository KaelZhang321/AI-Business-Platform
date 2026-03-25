FROM maven:3.9-eclipse-temurin-17-alpine AS builder

WORKDIR /build

# 配置Maven阿里云镜像加速
RUN mkdir -p /root/.m2 && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /root/.m2/settings.xml && \
    echo '<settings><mirrors><mirror>' >> /root/.m2/settings.xml && \
    echo '<id>aliyun</id><mirrorOf>central</mirrorOf>' >> /root/.m2/settings.xml && \
    echo '<url>https://maven.aliyun.com/repository/public</url>' >> /root/.m2/settings.xml && \
    echo '</mirror></mirrors></settings>' >> /root/.m2/settings.xml

# 先复制pom.xml下载依赖（利用Docker缓存）
COPY pom.xml .
RUN mvn dependency:go-offline -B

# 复制源码并构建
COPY src ./src
RUN mvn package -DskipTests -B

# ── 运行时镜像 ──────────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine AS runtime

WORKDIR /app

COPY --from=builder /build/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", \
  "-XX:+UseG1GC", \
  "-XX:MaxRAMPercentage=75.0", \
  "-Djava.security.egd=file:/dev/./urandom", \
  "-jar", "app.jar"]
