# Build Fineract từ source (Gradle bootJar) → image chạy lab NPD.
# Context Kaniko = repo root (.). Build nặng: ~10–40 phút, cần RAM agent ≥6Gi.
#
#   docker build -f docker/fineract-server/Dockerfile -t fineract-server:local .

FROM azul/zulu-openjdk:25 AS builder
WORKDIR /src

# Wrapper + scripts trước để tận dụng cache layer khi chỉ đổi source
COPY gradlew settings.gradle build.gradle gradle.properties ./
COPY gradle ./gradle
COPY buildSrc ./buildSrc

# Module Gradle (multi-project) — COPY cả tree rồi build
COPY . .

ENV GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.workers.max=2 -Xmx4g"
RUN chmod +x ./gradlew \
 && ./gradlew --no-daemon --console=plain \
      :fineract-provider:bootJar \
      -x test -x cucumber -x rat \
      -x spotlessJava -x spotlessJavaCheck \
      -x buildJavaSdk \
 && JAR="$(ls fineract-provider/build/libs/fineract-provider*.jar | grep -v plain | head -1)" \
 && cp "$JAR" /tmp/fineract-provider.jar

FROM azul/zulu-openjdk-alpine:25-jre-headless
WORKDIR /app
COPY --from=builder /tmp/fineract-provider.jar /app/fineract-provider.jar
USER nobody:nogroup
EXPOSE 8080 8443
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -Duser.home=/tmp -Dfile.encoding=UTF-8 -Duser.timezone=UTC"
ENTRYPOINT ["java", "-jar", "/app/fineract-provider.jar"]
