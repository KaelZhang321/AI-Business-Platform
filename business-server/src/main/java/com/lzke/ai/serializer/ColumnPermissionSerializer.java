package com.lzke.ai.serializer;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.BeanProperty;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.ser.ContextualSerializer;
import com.lzke.ai.annotation.ColumnPermission;
import com.lzke.ai.security.UserPrincipal;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.io.IOException;
import java.util.Arrays;
import java.util.Set;

/**
 * 列级权限 Jackson 序列化器。
 * 检查当前用户角色是否在 @ColumnPermission.roles() 中，
 * 不满足时输出 null 或 fallback 值。
 */
public class ColumnPermissionSerializer extends JsonSerializer<Object> implements ContextualSerializer {

    private Set<String> allowedRoles;
    private String fallback;

    public ColumnPermissionSerializer() {
    }

    public ColumnPermissionSerializer(String[] roles, String fallback) {
        this.allowedRoles = Set.copyOf(Arrays.asList(roles));
        this.fallback = fallback;
    }

    @Override
    public void serialize(Object value, JsonGenerator gen, SerializerProvider serializers) throws IOException {
        if (hasPermission()) {
            gen.writeObject(value);
        } else if (fallback != null && !fallback.isEmpty()) {
            gen.writeString(fallback);
        } else {
            gen.writeNull();
        }
    }

    @Override
    public JsonSerializer<?> createContextual(SerializerProvider prov, BeanProperty property)
            throws JsonMappingException {
        if (property == null) {
            return prov.findNullValueSerializer(null);
        }
        ColumnPermission annotation = property.getAnnotation(ColumnPermission.class);
        if (annotation == null) {
            annotation = property.getContextAnnotation(ColumnPermission.class);
        }
        if (annotation != null) {
            return new ColumnPermissionSerializer(annotation.roles(), annotation.fallback());
        }
        return prov.findValueSerializer(property.getType(), property);
    }

    private boolean hasPermission() {
        if (allowedRoles == null || allowedRoles.isEmpty()) {
            return true;
        }
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof UserPrincipal principal) {
            return allowedRoles.contains(principal.getRole());
        }
        return false;
    }
}
