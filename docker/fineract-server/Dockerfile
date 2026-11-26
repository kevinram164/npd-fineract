# Runtime image — JAR đã build sẵn bởi Gradle (Jenkins container `gradle` + docker.sock).
# Không chạy Gradle trong Kaniko (QueryDSL codegen cần Testcontainers/Docker).
FROM azul/zulu-openjdk-alpine:25-jre-headless
WORKDIR /app
COPY fineract-provider.jar /app/fineract-provider.jar
USER nobody:nogroup
EXPOSE 8080 8443
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -Duser.home=/tmp -Dfile.encoding=UTF-8 -Duser.timezone=UTC"
ENTRYPOINT ["java", "-jar", "/app/fineract-provider.jar"]
