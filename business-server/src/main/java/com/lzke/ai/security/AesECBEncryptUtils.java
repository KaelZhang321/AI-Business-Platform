package com.lzke.ai.security;

import cn.hutool.core.util.StrUtil;
import lombok.extern.slf4j.Slf4j;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * @author Mayichen
 * @Date 2024-05-20 09:36
 * AES
 */
@Slf4j
public class AesECBEncryptUtils {
    private static final String ALGORITHM = "AES";
    //ECB确定性加密
    private static final String TRANSFORMATION = "AES/ECB/PKCS5Padding";


    /**
     * 加密
     *
     * @param plainText
     * @return
     */
    public static String encrypt(String plainText) {
        if (StrUtil.isBlank(plainText)) {
            return "";
        }
        return AesECBEncryptUtils.encrypt(plainText, EncryptedString.key);
    }

    /**
     * 加密方法，接受明文和密码，生成Base64编码的密文。
     *
     * @param plainText
     * @param password
     * @return
     * @throws Exception
     */
    public static String encrypt(String plainText, String password) {
        byte[] secretKey = EncryptedString.generateKeyFromPassword(password);
        try {
            SecretKeySpec key = new SecretKeySpec(secretKey, ALGORITHM);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, key);
            byte[] encryptedBytes = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            // 将密文编码为Base64字符串
            return Base64.getEncoder().encodeToString(encryptedBytes);
        } catch (Exception e) {
        	log.warn("加密失败: " + plainText);
            return plainText;
        }
        

    }

    public static String decrypt(String encryptedString) {
        if (StrUtil.isBlank(encryptedString)) {
            return "";
        }
        return AesECBEncryptUtils.decrypt(encryptedString, EncryptedString.key);
    }

    /**
     * 解密方法，接受Base64编码的密文和密码，还原明文。
     *
     * @param encryptedString
     * @param password
     * @return
     * @throws Exception
     */
    public static String decrypt(String encryptedString, String password) {
        if (StrUtil.isBlank(encryptedString)) {
            return "";
        }
        byte[] secretKey = EncryptedString.generateKeyFromPassword(password);
        byte[] encryptedBytes = Base64.getDecoder().decode(encryptedString);

        try {
            SecretKeySpec key = new SecretKeySpec(secretKey, ALGORITHM);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, key);
            byte[] decrypted = cipher.doFinal(encryptedBytes);
            return new String(decrypted, StandardCharsets.UTF_8);
        } catch (Exception e) {
            log.warn("解密失败: " + encryptedString, e);
        }
        return encryptedString;
    }


    public static void main(String[] args) {
        System.out.println(AesECBEncryptUtils.encrypt("leczcore.2024"));
    }
}
