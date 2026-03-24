package com.lzke.ai.security;

import com.baomidou.mybatisplus.extension.plugins.inner.InnerInterceptor;
import lombok.extern.slf4j.Slf4j;
import net.sf.jsqlparser.expression.StringValue;
import net.sf.jsqlparser.expression.operators.conditional.AndExpression;
import net.sf.jsqlparser.expression.operators.relational.EqualsTo;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;
import net.sf.jsqlparser.schema.Column;
import net.sf.jsqlparser.statement.Statement;
import net.sf.jsqlparser.statement.select.PlainSelect;
import net.sf.jsqlparser.statement.select.Select;
import org.apache.ibatis.executor.Executor;
import org.apache.ibatis.mapping.BoundSql;
import org.apache.ibatis.mapping.MappedStatement;
import org.apache.ibatis.mapping.SqlSource;
import org.apache.ibatis.session.ResultHandler;
import org.apache.ibatis.session.RowBounds;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.Set;

/**
 * 行级数据权限拦截器 — 基于 JSqlParser 安全改写 SQL。
 * <p>
 * admin 全量访问；user/viewer 自动追加 WHERE user_id = ? 条件。
 * 仅对涉及 tasks / audit_logs / conversations 表的查询生效。
 */
@Slf4j
public class DataPermissionInterceptor implements InnerInterceptor {

    private static final Set<String> APPLICABLE_TABLES = Set.of("tasks", "audit_logs", "conversations");

    @Override
    public void beforeQuery(Executor executor, MappedStatement ms, Object parameter,
                            RowBounds rowBounds, ResultHandler resultHandler, BoundSql boundSql) {
        UserPrincipal user = getCurrentUser();
        if (user == null || "admin".equals(user.getRole())) {
            return;
        }

        String originalSql = boundSql.getSql();
        if (!containsApplicableTable(originalSql)) {
            return;
        }

        try {
            String newSql = appendPermissionCondition(originalSql, user.getId().toString());
            if (!newSql.equals(originalSql)) {
                // 通过 MetaObject 安全修改 BoundSql 中的 sql 字段
                var metaBoundSql = ms.getConfiguration().newMetaObject(boundSql);
                metaBoundSql.setValue("sql", newSql);
                log.debug("行级权限: userId={}", user.getId());
            }
        } catch (Exception e) {
            log.warn("行级权限SQL解析失败，跳过改写: {}", e.getMessage());
        }
    }

    /**
     * 使用 JSqlParser 安全地追加 WHERE user_id = 'xxx' 条件
     */
    private String appendPermissionCondition(String sql, String userId) throws Exception {
        Statement stmt = CCJSqlParserUtil.parse(sql);
        if (!(stmt instanceof Select select)) {
            return sql;
        }
        if (!(select.getSelectBody() instanceof PlainSelect plainSelect)) {
            return sql;
        }

        EqualsTo equalsTo = new EqualsTo();
        equalsTo.setLeftExpression(new Column("user_id"));
        equalsTo.setRightExpression(new StringValue(userId));

        if (plainSelect.getWhere() == null) {
            plainSelect.setWhere(equalsTo);
        } else {
            plainSelect.setWhere(new AndExpression(equalsTo, plainSelect.getWhere()));
        }
        return select.toString();
    }

    private boolean containsApplicableTable(String sql) {
        String lower = sql.toLowerCase();
        for (String table : APPLICABLE_TABLES) {
            if (lower.contains(table)) {
                return true;
            }
        }
        return false;
    }

    private UserPrincipal getCurrentUser() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof UserPrincipal principal) {
            return principal;
        }
        return null;
    }
}
