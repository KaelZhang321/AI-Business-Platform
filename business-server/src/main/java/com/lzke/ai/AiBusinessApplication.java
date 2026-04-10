package com.lzke.ai;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.web.client.RestTemplate;

@SpringBootApplication(scanBasePackages = { "com.lzke.ai", "com.lecz.service" })
@MapperScan({ "com.lzke.ai.infrastructure.persistence.mapper", "com.lzke.ai.application.rule.dao" })
public class AiBusinessApplication {

	// 定义超时时间（按需调整，示例：连接超时3秒，读取超时10秒）
	private static final int CONNECT_TIMEOUT = 5000; // 5秒
	private static final int READ_TIMEOUT = 60000; // 60秒

	private static final Integer CORE_POOL_SIZE = 4;
	private static final Integer MAX_IMUM_POOL_SIZE = 10000;
	private static final Integer KEEP_ALIVE_TIME = 30;

	private static ExecutorService pool;

	@Bean
	public ExecutorService getExecutorService() {
		return pool;
	}

	static {
		pool = new ThreadPoolExecutor(CORE_POOL_SIZE, MAX_IMUM_POOL_SIZE, KEEP_ALIVE_TIME, TimeUnit.SECONDS,
				new LinkedBlockingQueue<>(), Executors.defaultThreadFactory(), new ThreadPoolExecutor.AbortPolicy());
	}

	@Bean
	public RestTemplate restTemplate() {

		RestTemplate restTemplate = new RestTemplate();

		// 1. 配置请求工厂，设置超时时间
		ClientHttpRequestFactory factory = createRequestFactory();
		restTemplate.setRequestFactory(factory);

		restTemplate.getMessageConverters().replaceAll(converter -> {
			if (converter instanceof StringHttpMessageConverter) {
				return new StringHttpMessageConverter(StandardCharsets.UTF_8);
			}
			return converter;
		});

		return restTemplate;
	}

	// 封装请求工厂创建逻辑，设置超时
	private ClientHttpRequestFactory createRequestFactory() {
		SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
		// 设置连接超时
		factory.setConnectTimeout(CONNECT_TIMEOUT);
		// 设置读取超时
		factory.setReadTimeout(READ_TIMEOUT);
		// 可选：设置请求超时（Spring 5.2+ 支持，等价于读取超时）
		// factory.setConnectionRequestTimeout(CONNECT_TIMEOUT);
		return factory;
	}

	public static void main(String[] args) {
		SpringApplication.run(AiBusinessApplication.class, args);
	}

}
