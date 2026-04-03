package com.lzke.ai.application.dto;

import com.lzke.ai.domain.entity.UiNodeBinding;
import com.lzke.ai.domain.entity.UiPage;
import com.lzke.ai.domain.entity.UiPageNode;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiBuilderPageDetailResponse {

    private UiPage page;
    private List<UiPageNode> nodes;
    private List<UiNodeBinding> bindings;
}
