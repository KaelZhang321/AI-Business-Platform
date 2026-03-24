package com.lzke.ai.serializer;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.BeanProperty;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.ser.ContextualSerializer;
import com.lzke.ai.annotation.Sensitive;
import com.lzke.ai.annotation.SensitiveType;
import com.lzke.ai.security.DataMaskingUtil;

import java.io.IOException;

/**
 * Jackson 脱敏序列化器 — 配合 @Sensitive 注解自动对字段值脱敏。
 */
public class SensitiveJsonSerializer extends JsonSerializer<String> implements ContextualSerializer {

    private SensitiveType type;

    public SensitiveJsonSerializer() {}

    public SensitiveJsonSerializer(SensitiveType type) {
        this.type = type;
    }

    @Override
    public void serialize(String value, JsonGenerator gen, SerializerProvider serializers) throws IOException {
        if (value == null) {
            gen.writeNull();
            return;
        }
        String masked = switch (type) {
            case PHONE -> DataMaskingUtil.maskPhone(value);
            case ID_CARD -> DataMaskingUtil.maskIdCard(value);
            case NAME -> DataMaskingUtil.maskName(value);
            case EMAIL -> DataMaskingUtil.maskEmail(value);
        };
        gen.writeString(masked);
    }

    @Override
    public JsonSerializer<?> createContextual(SerializerProvider prov, BeanProperty property) {
        if (property == null) return this;
        Sensitive annotation = property.getAnnotation(Sensitive.class);
        if (annotation == null) {
            annotation = property.getContextAnnotation(Sensitive.class);
        }
        if (annotation != null) {
            return new SensitiveJsonSerializer(annotation.type());
        }
        return this;
    }
}
