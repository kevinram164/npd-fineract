# Runtime image — JAR đã build sẵn bởi Gradle (Jenkins container `gradle` + DinD).
# OTel Java agent → OTLP collector platform → Instana + Elastic APM.
ARG OTEL_JAVA_AGENT_VERSION=2.34.0

FROM curlimages/curl:8.11.1 AS otel
ARG OTEL_JAVA_AGENT_VERSION
USER root
RUN mkdir -p /otel \
 && curl -fsSL -o /otel/opentelemetry-javaagent.jar \
      "https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v${OTEL_JAVA_AGENT_VERSION}/opentelemetry-javaagent.jar" \
 && chmod 644 /otel/opentelemetry-javaagent.jar

FROM azul/zulu-openjdk-alpine:25-jre-headless
WORKDIR /app
COPY --from=otel /otel/opentelemetry-javaagent.jar /otel/opentelemetry-javaagent.jar
COPY fineract-provider.jar /app/fineract-provider.jar
USER nobody:nogroup
EXPOSE 8080 8443
# Heap mặc định; Helm ghi đè JAVA_TOOL_OPTIONS (kèm -javaagent).
ENV JAVA_TOOL_OPTIONS="-javaagent:/otel/opentelemetry-javaagent.jar -XX:MaxRAMPercentage=75.0 -Duser.home=/tmp -Dfile.encoding=UTF-8 -Duser.timezone=UTC"
ENTRYPOINT ["java", "-jar", "/app/fineract-provider.jar"]
