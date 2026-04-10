package com.lzke.ai.application.rule.po;

import java.io.Serializable;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;

import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import lombok.experimental.Accessors;

@Getter
@Setter
@ToString
@Accessors(chain = true)
@TableName("rule_node")
public class RuleNode extends Model<RuleNode> {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private Long ruleId;

    private String nodeName;

    private String nodeType;
    
    private String nodeGroup;

    // 节点sql
    private String nodeSql;
    
    private Integer sortOrder;
    
    private String nodeConfig;
    
    private String ruleVersion;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
