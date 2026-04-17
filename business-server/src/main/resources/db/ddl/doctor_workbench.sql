CREATE TABLE IF NOT EXISTS `doctor_role_card_config` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `role_id` varchar(64) NOT NULL COMMENT '角色ID',
  `role_code` varchar(64) DEFAULT NULL COMMENT '角色编码',
  `role_name` varchar(128) DEFAULT NULL COMMENT '角色名称',
  `card_schema_json` json DEFAULT NULL COMMENT '卡片配置json',
  `visible_flag` tinyint NOT NULL DEFAULT 1 COMMENT '是否展示',
  `status` varchar(32) NOT NULL DEFAULT 'active' COMMENT '状态',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  `created_by` varchar(64) DEFAULT NULL COMMENT '创建人',
  `created_by_name` varchar(64) DEFAULT NULL COMMENT '创建人名称',
  `updated_by` varchar(64) DEFAULT NULL COMMENT '更新人',
  `updated_by_name` varchar(64) DEFAULT NULL COMMENT '更新人名称',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_doctor_role_card_role` (`role_id`, `status`, `visible_flag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='医生角色卡片配置表';

CREATE TABLE IF NOT EXISTS `doctor_customer_card_customize` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `employee_id` varchar(64) NOT NULL COMMENT '登录员工ID',
  `employee_name` varchar(64) DEFAULT NULL COMMENT '登录员工名称',
  `customer_id_card` varchar(128) NOT NULL COMMENT '客户身份证号',
  `favorite_name` varchar(128) NOT NULL COMMENT '收藏名称',
  `card_json` json NOT NULL COMMENT '卡片json信息',
  `status` varchar(32) NOT NULL DEFAULT 'active' COMMENT '状态',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_doctor_customer_favorite` (`employee_id`, `customer_id_card`, `favorite_name`),
  KEY `idx_doctor_customer_card_employee_customer` (`employee_id`, `customer_id_card`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='医生客户定制卡片表';

CREATE TABLE IF NOT EXISTS `doctor_customer_note` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `employee_id` varchar(64) NOT NULL COMMENT '登录员工ID',
  `employee_name` varchar(64) DEFAULT NULL COMMENT '登录员工名称',
  `customer_id_card` varchar(128) NOT NULL COMMENT '客户身份证号',
  `note_content` text NOT NULL COMMENT '便签内容',
  `sort_order` int NOT NULL DEFAULT 0 COMMENT '排序',
  `status` varchar(32) NOT NULL DEFAULT 'active' COMMENT '状态',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_doctor_customer_note_employee_customer` (`employee_id`, `customer_id_card`, `status`),
  KEY `idx_doctor_customer_note_sort` (`sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='医生客户便签表';
