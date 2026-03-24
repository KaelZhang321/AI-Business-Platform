package com.lzke.ai.security;

/**
 * 数据脱敏工具类 — 手机号/身份证/姓名/邮箱脱敏。
 */
public final class DataMaskingUtil {

    private DataMaskingUtil() {}

    /** 手机号脱敏: 138****1234 */
    public static String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) return phone;
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }

    /** 身份证脱敏: 110***********1234 */
    public static String maskIdCard(String idCard) {
        if (idCard == null || idCard.length() < 8) return idCard;
        return idCard.substring(0, 3) + "*".repeat(idCard.length() - 7) + idCard.substring(idCard.length() - 4);
    }

    /** 姓名脱敏: 张* / 欧阳** */
    public static String maskName(String name) {
        if (name == null || name.isEmpty()) return name;
        if (name.length() == 1) return name;
        if (name.length() == 2) return name.charAt(0) + "*";
        return name.charAt(0) + "*".repeat(name.length() - 1);
    }

    /** 邮箱脱敏: u***@example.com */
    public static String maskEmail(String email) {
        if (email == null || !email.contains("@")) return email;
        int atIdx = email.indexOf('@');
        if (atIdx <= 1) return email;
        return email.charAt(0) + "***" + email.substring(atIdx);
    }
}
