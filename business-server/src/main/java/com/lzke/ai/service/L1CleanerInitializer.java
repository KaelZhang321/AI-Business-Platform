package com.lzke.ai.service;

import java.io.File;
import java.nio.file.Paths;

import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;

@Component
public class L1CleanerInitializer {
    @PostConstruct
    public void init() throws Exception {
//    	File resourcesDir = new File("src/main/resources");
//    	String absolutePath = resourcesDir.getAbsolutePath();
//    	
//        L1RuleCleaner.initializeOnce(Paths.get(absolutePath+"/"));
    }
}