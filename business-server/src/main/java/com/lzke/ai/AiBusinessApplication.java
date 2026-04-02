package com.lzke.ai;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import com.dtflys.forest.springboot.annotation.ForestScan;

@SpringBootApplication(scanBasePackages = {"com.lzke.ai","com.lecz.service"})
@MapperScan("com.lzke.ai.infrastructure.persistence.mapper")
public class AiBusinessApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiBusinessApplication.class, args);
    }
}
