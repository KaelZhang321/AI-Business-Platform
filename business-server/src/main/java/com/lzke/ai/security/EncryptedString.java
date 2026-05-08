package com.lzke.ai.security;

import java.nio.charset.StandardCharsets;

import lombok.Data;

@Data
public class  EncryptedString {

    /**
     * 长度为16个字符
     */
    public static  String key = "SecuR2`4LeCzCoRe";

    /**
     * 长度为16个字符
     */
    public static  String iv  = "leczker_platform";

    public static  int KEY_SIZE = 16; // AES-128

    /**
     * 根据任意长度的密码生成固定长度的密钥（AES-128）
     * @param password
     * @return
     */
    public static byte[] generateKeyFromPassword(String password) {

        return generateKeyFromPassword(password,KEY_SIZE);
    }
    public static byte[] generateKeyFromPassword(String password,int keySize) {
        byte[] key = new byte[keySize];
        byte[] passwordBytes = password.getBytes(StandardCharsets.UTF_8);
        System.arraycopy(passwordBytes, 0, key, 0, Math.min(passwordBytes.length, key.length));
        return key;
    }
}
