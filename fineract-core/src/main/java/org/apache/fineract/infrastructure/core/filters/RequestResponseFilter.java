/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements. See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership. The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License. You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package org.apache.fineract.infrastructure.core.filters;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.filter.OncePerRequestFilter;

@RequiredArgsConstructor
@Slf4j
public class RequestResponseFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        final long started = System.currentTimeMillis();
        log.debug("Received request: [{}], [{}]", request.getMethod(), request.getRequestURI());
        try {
            filterChain.doFilter(request, response);
        } finally {
            // INFO: một dòng / request API → stdout có %X{correlationId} + %X{trace_id} (OTel MDC / script
            // traceparent). Pattern console in MDC; kubectl/Instana Logs soi cùng Trace ID với bot `trace=`.
            if (shouldLogAccess(request)) {
                log.info("HTTP {} {} status={} durationMs={} flow={}", request.getMethod(), request.getRequestURI(),
                        response.getStatus(), System.currentTimeMillis() - started, request.getHeader("X-Business-Flow"));
            }
            log.debug("Sent response: [{}] for [{}], [{}]", response.getStatus(), request.getMethod(), request.getRequestURI());
        }
    }

    private static boolean shouldLogAccess(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (path == null) {
            return false;
        }
        return !(path.contains("/actuator") || path.contains("/prometheus") || path.endsWith("/health"));
    }
}
