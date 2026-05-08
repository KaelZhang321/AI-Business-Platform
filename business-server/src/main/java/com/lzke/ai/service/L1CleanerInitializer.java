package com.lzke.ai.service;

import java.io.InputStream;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;

@Component
public class L1CleanerInitializer {

    private static final String STANDARD_DICT_PATH = "data/standard_dict.csv";
    private static final String ALIAS_DICT_PATH = "data/alias_dict.csv";

    @PostConstruct
    public void init() throws Exception {
        ClassPathResource standardDict = new ClassPathResource(STANDARD_DICT_PATH);
        ClassPathResource aliasDict = new ClassPathResource(ALIAS_DICT_PATH);
        if (!standardDict.exists() || !aliasDict.exists()) {
            throw new IllegalStateException("L1清洗字典资源不存在: " + STANDARD_DICT_PATH + ", " + ALIAS_DICT_PATH);
        }

        try (InputStream standardInputStream = standardDict.getInputStream();
             InputStream aliasInputStream = aliasDict.getInputStream()) {
            L1RuleCleaner.initializeOnce(standardInputStream, aliasInputStream);
        }
    }
}
