package com.lzke.ai;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.lzke.ai.mapper")
public class AiBusinessApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiBusinessApplication.class, args);
    }
}
