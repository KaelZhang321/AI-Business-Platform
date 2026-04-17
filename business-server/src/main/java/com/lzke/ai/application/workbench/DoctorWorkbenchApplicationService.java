package com.lzke.ai.application.workbench;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lecz.iam.system.employee.service.ISysEmployeeHttpService;
import com.lecz.iam.system.employee.vo.SysEmployeeVO;
import com.lecz.service.tools.core.dto.ResponseDto;
import com.lecz.service.tools.core.utils.AuthUtil;
import com.lzke.ai.application.workbench.dto.DoctorCustomerCardCustomizeQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorCustomerCardCustomizeRequest;
import com.lzke.ai.application.workbench.dto.DoctorCustomerNoteQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorCustomerNoteRequest;
import com.lzke.ai.application.workbench.dto.DoctorRoleCardConfigQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorRoleCardConfigRequest;
import com.lzke.ai.domain.entity.DoctorCustomerCardCustomize;
import com.lzke.ai.domain.entity.DoctorCustomerNote;
import com.lzke.ai.domain.entity.DoctorRoleCardConfig;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.infrastructure.persistence.mapper.DoctorCustomerCardCustomizeMapper;
import com.lzke.ai.infrastructure.persistence.mapper.DoctorCustomerNoteMapper;
import com.lzke.ai.infrastructure.persistence.mapper.DoctorRoleCardConfigMapper;
import com.lzke.ai.interfaces.dto.PageResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanWrapper;
import org.springframework.beans.PropertyAccessorFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.Duration;
import java.util.List;
import java.util.Objects;

/**
 * 医生工作台配置应用服务。
 *
 * <p>统一维护角色卡片、客户定制卡片和客户便签三类配置，
 * 方便前端一个模块完成医生工作台能力搭建。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DoctorWorkbenchApplicationService {

    private static final String USER_INFO_CACHE_PREFIX = "auth:info:user:";
    private static final Duration USER_INFO_CACHE_TTL = Duration.ofHours(8);

    private final DoctorRoleCardConfigMapper doctorRoleCardConfigMapper;
    private final DoctorCustomerCardCustomizeMapper doctorCustomerCardCustomizeMapper;
    private final DoctorCustomerNoteMapper doctorCustomerNoteMapper;
    private final ISysEmployeeHttpService sysEmployeeHttpService;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate stringRedisTemplate;

    public PageResult<DoctorRoleCardConfig> listRoleCardConfigs(DoctorRoleCardConfigQueryRequest request) {
        DoctorRoleCardConfigQueryRequest query = request == null ? new DoctorRoleCardConfigQueryRequest() : request;
        Page<DoctorRoleCardConfig> page = new Page<>(query.getPage(), query.getSize());
        LambdaQueryWrapper<DoctorRoleCardConfig> wrapper = new LambdaQueryWrapper<DoctorRoleCardConfig>()
                .eq(StringUtils.hasText(query.getRoleId()), DoctorRoleCardConfig::getRoleId, query.getRoleId())
                .eq(StringUtils.hasText(query.getRoleCode()), DoctorRoleCardConfig::getRoleCode, query.getRoleCode())
                .eq(StringUtils.hasText(query.getStatus()), DoctorRoleCardConfig::getStatus, query.getStatus())
                .eq(query.getVisibleFlag() != null, DoctorRoleCardConfig::getVisibleFlag, query.getVisibleFlag())
                .orderByDesc(DoctorRoleCardConfig::getUpdatedAt);
        Page<DoctorRoleCardConfig> result = doctorRoleCardConfigMapper.selectPage(page, wrapper);
        return PageResult.of(result.getRecords(), result.getTotal(), (int) result.getCurrent(), (int) result.getSize());
    }

    public DoctorRoleCardConfig getRoleCardConfig(String id) {
        DoctorRoleCardConfig entity = doctorRoleCardConfigMapper.selectById(id);
        if (entity == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到医生角色卡片配置: " + id);
        }
        return entity;
    }

    public List<DoctorRoleCardConfig> listRoleCardConfigsByRole(String roleId) {
        if (!StringUtils.hasText(roleId)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "roleId不能为空");
        }
        return doctorRoleCardConfigMapper.selectList(new LambdaQueryWrapper<DoctorRoleCardConfig>()
                .eq(DoctorRoleCardConfig::getRoleId, roleId)
                .eq(DoctorRoleCardConfig::getStatus, "active")
                .eq(DoctorRoleCardConfig::getVisibleFlag, 1)
                .orderByDesc(DoctorRoleCardConfig::getUpdatedAt));
    }

    @Transactional
    public DoctorRoleCardConfig createRoleCardConfig(DoctorRoleCardConfigRequest request) {
        validateRoleCardConfigRequest(request);
        DoctorRoleCardConfig entity = new DoctorRoleCardConfig();
        copyRoleCardConfig(entity, request);
        doctorRoleCardConfigMapper.insert(entity);
        return entity;
    }

    @Transactional
    public DoctorRoleCardConfig updateRoleCardConfig(String id, DoctorRoleCardConfigRequest request) {
        validateRoleCardConfigRequest(request);
        DoctorRoleCardConfig entity = getRoleCardConfig(id);
        copyRoleCardConfig(entity, request);
        doctorRoleCardConfigMapper.updateById(entity);
        return getRoleCardConfig(id);
    }

    @Transactional
    public void deleteRoleCardConfig(String id) {
        if (doctorRoleCardConfigMapper.deleteById(id) <= 0) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到医生角色卡片配置: " + id);
        }
    }

    public PageResult<DoctorCustomerCardCustomize> listCustomerCardCustomizes(DoctorCustomerCardCustomizeQueryRequest request) {
        DoctorCustomerCardCustomizeQueryRequest query = request == null ? new DoctorCustomerCardCustomizeQueryRequest() : request;
        String currentEmployeeId = getCurrentEmployeeId();
        Page<DoctorCustomerCardCustomize> page = new Page<>(query.getPage(), query.getSize());
        LambdaQueryWrapper<DoctorCustomerCardCustomize> wrapper = new LambdaQueryWrapper<DoctorCustomerCardCustomize>()
                .eq(DoctorCustomerCardCustomize::getEmployeeId, currentEmployeeId)
                .eq(StringUtils.hasText(query.getCustomerIdCard()), DoctorCustomerCardCustomize::getCustomerIdCard, query.getCustomerIdCard())
                .like(StringUtils.hasText(query.getFavoriteName()), DoctorCustomerCardCustomize::getFavoriteName, query.getFavoriteName())
                .eq(StringUtils.hasText(query.getStatus()), DoctorCustomerCardCustomize::getStatus, query.getStatus())
                .orderByDesc(DoctorCustomerCardCustomize::getUpdatedAt);
        Page<DoctorCustomerCardCustomize> result = doctorCustomerCardCustomizeMapper.selectPage(page, wrapper);
        return PageResult.of(result.getRecords(), result.getTotal(), (int) result.getCurrent(), (int) result.getSize());
    }

    public DoctorCustomerCardCustomize getCustomerCardCustomize(String id) {
        DoctorCustomerCardCustomize entity = doctorCustomerCardCustomizeMapper.selectById(id);
        if (entity == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到医生客户定制卡片: " + id);
        }
        return entity;
    }

    public List<DoctorCustomerCardCustomize> listCustomerCardCustomizesByCustomer(String customerIdCard) {
        String currentEmployeeId = getCurrentEmployeeId();
        if (!StringUtils.hasText(customerIdCard)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "customerIdCard不能为空");
        }
        return doctorCustomerCardCustomizeMapper.selectList(new LambdaQueryWrapper<DoctorCustomerCardCustomize>()
                .eq(DoctorCustomerCardCustomize::getEmployeeId, currentEmployeeId)
                .eq(DoctorCustomerCardCustomize::getCustomerIdCard, customerIdCard)
                .eq(DoctorCustomerCardCustomize::getStatus, "active")
                .orderByDesc(DoctorCustomerCardCustomize::getUpdatedAt));
    }

    @Transactional
    public DoctorCustomerCardCustomize createCustomerCardCustomize(DoctorCustomerCardCustomizeRequest request) {
        validateCustomerCardCustomizeRequest(request);
        DoctorCustomerCardCustomize entity = new DoctorCustomerCardCustomize();
        copyCustomerCardCustomize(entity, request);
        doctorCustomerCardCustomizeMapper.insert(entity);
        return entity;
    }

    @Transactional
    public DoctorCustomerCardCustomize updateCustomerCardCustomize(String id, DoctorCustomerCardCustomizeRequest request) {
        validateCustomerCardCustomizeRequest(request);
        DoctorCustomerCardCustomize entity = getCustomerCardCustomize(id);
        copyCustomerCardCustomize(entity, request);
        doctorCustomerCardCustomizeMapper.updateById(entity);
        return getCustomerCardCustomize(id);
    }

    @Transactional
    public void deleteCustomerCardCustomize(String id) {
        if (doctorCustomerCardCustomizeMapper.deleteById(id) <= 0) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到医生客户定制卡片: " + id);
        }
    }

    public PageResult<DoctorCustomerNote> listCustomerNotes(DoctorCustomerNoteQueryRequest request) {
        DoctorCustomerNoteQueryRequest query = request == null ? new DoctorCustomerNoteQueryRequest() : request;
        String currentEmployeeId = getCurrentEmployeeId();
        Page<DoctorCustomerNote> page = new Page<>(query.getPage(), query.getSize());
        LambdaQueryWrapper<DoctorCustomerNote> wrapper = new LambdaQueryWrapper<DoctorCustomerNote>()
                .eq(DoctorCustomerNote::getEmployeeId, currentEmployeeId)
                .eq(StringUtils.hasText(query.getCustomerIdCard()), DoctorCustomerNote::getCustomerIdCard, query.getCustomerIdCard())
                .like(StringUtils.hasText(query.getKeyword()), DoctorCustomerNote::getNoteContent, query.getKeyword())
                .eq(StringUtils.hasText(query.getStatus()), DoctorCustomerNote::getStatus, query.getStatus())
                .orderByAsc(DoctorCustomerNote::getSortOrder)
                .orderByDesc(DoctorCustomerNote::getUpdatedAt);
        Page<DoctorCustomerNote> result = doctorCustomerNoteMapper.selectPage(page, wrapper);
        return PageResult.of(result.getRecords(), result.getTotal(), (int) result.getCurrent(), (int) result.getSize());
    }

    public DoctorCustomerNote getCustomerNote(String id) {
        DoctorCustomerNote entity = doctorCustomerNoteMapper.selectById(id);
        if (entity == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到医生客户便签: " + id);
        }
        return entity;
    }

    public List<DoctorCustomerNote> listCustomerNotesByCustomer(String customerIdCard) {
        String currentEmployeeId = getCurrentEmployeeId();
        if (!StringUtils.hasText(customerIdCard)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "customerIdCard不能为空");
        }
        return doctorCustomerNoteMapper.selectList(new LambdaQueryWrapper<DoctorCustomerNote>()
                .eq(DoctorCustomerNote::getEmployeeId, currentEmployeeId)
                .eq(DoctorCustomerNote::getCustomerIdCard, customerIdCard)
                .eq(DoctorCustomerNote::getStatus, "active")
                .orderByAsc(DoctorCustomerNote::getSortOrder)
                .orderByDesc(DoctorCustomerNote::getUpdatedAt));
    }

    @Transactional
    public DoctorCustomerNote createCustomerNote(DoctorCustomerNoteRequest request) {
        validateCustomerNoteRequest(request);
        DoctorCustomerNote entity = new DoctorCustomerNote();
        copyCustomerNote(entity, request);
        doctorCustomerNoteMapper.insert(entity);
        return entity;
    }

    @Transactional
    public DoctorCustomerNote updateCustomerNote(String id, DoctorCustomerNoteRequest request) {
        validateCustomerNoteRequest(request);
        DoctorCustomerNote entity = getCustomerNote(id);
        copyCustomerNote(entity, request);
        doctorCustomerNoteMapper.updateById(entity);
        return getCustomerNote(id);
    }

    @Transactional
    public void deleteCustomerNote(String id) {
        if (doctorCustomerNoteMapper.deleteById(id) <= 0) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到医生客户便签: " + id);
        }
    }

    private void validateRoleCardConfigRequest(DoctorRoleCardConfigRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "角色卡片配置请求不能为空");
        }
        if (!StringUtils.hasText(request.getRoleId())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "roleId不能为空");
        }
        if (!StringUtils.hasText(request.getCardSchemaJson())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "cardSchemaJson不能为空");
        }
    }

    private void validateCustomerCardCustomizeRequest(DoctorCustomerCardCustomizeRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "客户定制卡片请求不能为空");
        }
        if (!StringUtils.hasText(request.getCustomerIdCard())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "customerIdCard不能为空");
        }
        if (!StringUtils.hasText(request.getFavoriteName())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "favoriteName不能为空");
        }
        if (!StringUtils.hasText(request.getCardJson())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "cardJson不能为空");
        }
    }

    private void validateCustomerNoteRequest(DoctorCustomerNoteRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "客户便签请求不能为空");
        }
        if (!StringUtils.hasText(request.getCustomerIdCard())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "customerIdCard不能为空");
        }
        if (!StringUtils.hasText(request.getNoteContent())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "noteContent不能为空");
        }
    }

    private void copyRoleCardConfig(DoctorRoleCardConfig entity, DoctorRoleCardConfigRequest request) {
        entity.setRoleId(trimToNull(request.getRoleId()));
        entity.setRoleCode(trimToNull(request.getRoleCode()));
        entity.setRoleName(trimToNull(request.getRoleName()));
        entity.setCardSchemaJson(trimToNull(request.getCardSchemaJson()));
        entity.setVisibleFlag(request.getVisibleFlag() == null ? 1 : request.getVisibleFlag());
        entity.setStatus(StringUtils.hasText(request.getStatus()) ? request.getStatus().trim() : "active");
        entity.setRemark(trimToNull(request.getRemark()));
        entity.setCreatedBy(trimToNull(request.getCreatedBy()));
        entity.setCreatedByName(trimToNull(request.getCreatedByName()));
        entity.setUpdatedBy(trimToNull(request.getUpdatedBy()));
        entity.setUpdatedByName(trimToNull(request.getUpdatedByName()));
    }

    private void copyCustomerCardCustomize(DoctorCustomerCardCustomize entity, DoctorCustomerCardCustomizeRequest request) {
        entity.setEmployeeId(getCurrentEmployeeId());
        entity.setEmployeeName(getCurrentEmployeeName());
        entity.setCustomerIdCard(trimToNull(request.getCustomerIdCard()));
        entity.setFavoriteName(trimToNull(request.getFavoriteName()));
        entity.setCardJson(trimToNull(request.getCardJson()));
        entity.setStatus(StringUtils.hasText(request.getStatus()) ? request.getStatus().trim() : "active");
        entity.setRemark(trimToNull(request.getRemark()));
    }

    private void copyCustomerNote(DoctorCustomerNote entity, DoctorCustomerNoteRequest request) {
        entity.setEmployeeId(getCurrentEmployeeId());
        entity.setEmployeeName(getCurrentEmployeeName());
        entity.setCustomerIdCard(trimToNull(request.getCustomerIdCard()));
        entity.setNoteContent(trimToNull(request.getNoteContent()));
        entity.setSortOrder(defaultInt(request.getSortOrder()));
        entity.setStatus(StringUtils.hasText(request.getStatus()) ? request.getStatus().trim() : "active");
        entity.setRemark(trimToNull(request.getRemark()));
    }

    private String trimToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }

    private int defaultInt(Integer value) {
        return value == null ? 0 : value;
    }

    private String getCurrentEmployeeId() {
        Long currentUserId = AuthUtil.getUserId();
        if (currentUserId == null) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "未获取到当前登录员工信息");
        }
        return String.valueOf(currentUserId);
    }

    private String getCurrentEmployeeName() {
        SysEmployeeVO employee = getCurrentEmployeeVO();
        if (employee == null) {
            return null;
        }
        BeanWrapper beanWrapper = PropertyAccessorFactory.forBeanPropertyAccess(employee);
        return trimToNull(readStringProperty(beanWrapper, "realName", "name", "employeeName", "nickName", "nickname"));
    }

    private SysEmployeeVO getCurrentEmployeeVO() {
        String userId = getCurrentEmployeeId();
        String employeeStr = stringRedisTemplate.opsForValue().get(USER_INFO_CACHE_PREFIX + userId);
        if (StringUtils.hasText(employeeStr)) {
            try {
                return objectMapper.readValue(employeeStr, SysEmployeeVO.class);
            } catch (JsonProcessingException e) {
                log.warn("用户信息从 Redis 反序列化失败, userId={}", userId, e);
            }
        }
        ResponseDto<SysEmployeeVO> response = sysEmployeeHttpService.getById(Long.parseLong(userId));
        if (response != null && response.isSuccess() && response.getData() != null) {
            cacheUserInfo(userId, response.getData());
            return response.getData();
        }
        return null;
    }

    private void cacheUserInfo(String userId, SysEmployeeVO employee) {
        try {
            stringRedisTemplate.opsForValue().set(
                    USER_INFO_CACHE_PREFIX + userId,
                    objectMapper.writeValueAsString(employee),
                    USER_INFO_CACHE_TTL
            );
        } catch (JsonProcessingException ex) {
            log.warn("用户信息写入 Redis 失败, userId={}", userId, ex);
        }
    }

    private String readStringProperty(BeanWrapper beanWrapper, String... propertyNames) {
        for (String propertyName : propertyNames) {
            if (beanWrapper.isReadableProperty(propertyName)) {
                Object value = beanWrapper.getPropertyValue(propertyName);
                if (value != null) {
                    return Objects.toString(value, null);
                }
            }
        }
        return null;
    }
}
