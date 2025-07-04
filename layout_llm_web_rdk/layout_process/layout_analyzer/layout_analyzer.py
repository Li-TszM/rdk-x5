# -*- encoding: utf-8 -*-
# @Author: layout_analyzer
# 版面分析功能接口

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import json

import cv2
import numpy as np
import fitz  # PyMuPDF

# 添加 RapidLayout 路径
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from RapidLayout.rapid_layout import RapidLayout, VisLayout


@dataclass
class LayoutBlock:
    """版面块信息"""
    class_name: str  # 版面块类别
    box: np.ndarray  # 坐标 [x1, y1, x2, y2]
    score: float  # 置信度
    page_idx: int  # 所属页码（从0开始）
    block_idx: int  # 块索引


@dataclass
class PageLayoutResult:
    """单页版面分析结果"""
    page_idx: int  # 页码（从0开始）
    img: np.ndarray  # 页面图像
    blocks: List[LayoutBlock]  # 版面块列表


@dataclass
class PDFLayoutResult:
    """PDF文档版面分析结果"""
    pdf_path: str  # PDF路径
    total_pages: int  # 总页数
    page_results: List[PageLayoutResult]  # 每页的分析结果
    
    def get_blocks_by_class(self, class_name: str) -> List[LayoutBlock]:
        """获取指定类别的所有版面块"""
        return [block for page in self.page_results 
                for block in page.blocks 
                if block.class_name == class_name]
    
    def get_blocks_by_page(self, page_idx: int) -> List[LayoutBlock]:
        """获取指定页面的所有版面块"""
        if 0 <= page_idx < len(self.page_results):
            return self.page_results[page_idx].blocks
        return []
    
    def save_visualized_pdf(self, output_path: str) -> bool:
        """保存可视化后的PDF文件"""
        try:
            # 创建一个新的PDF文档
            doc = fitz.open()
            
            for page_result in self.page_results:
                # 将分析结果可视化
                vis_img = VisLayout.draw_detections(
                    page_result.img,
                    np.array([block.box for block in page_result.blocks]),
                    np.array([block.score for block in page_result.blocks]),
                    [block.class_name for block in page_result.blocks]
                )
                
                if vis_img is not None:
                    try:
                        # 转换为RGB格式（PyMuPDF要求）
                        vis_img = cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB)
                        
                        # 创建新页面
                        page = doc.new_page(width=vis_img.shape[1], height=vis_img.shape[0])
                        
                        # 将图像添加到页面 - 修改方法使其更可靠
                        # 首先保存为临时文件
                        temp_img_path = os.path.join(os.path.dirname(output_path), f"temp_img_{page_result.page_idx}.png")
                        cv2.imwrite(temp_img_path, vis_img)
                        
                        # 使用文件路径添加图像
                        rect = fitz.Rect(0, 0, vis_img.shape[1], vis_img.shape[0])
                        page.insert_image(rect, filename=temp_img_path)
                        
                        # 删除临时文件
                        if os.path.exists(temp_img_path):
                            os.remove(temp_img_path)
                    except Exception as inner_e:
                        print(f"添加页面时出错: {inner_e}, 类型: {type(inner_e)}")
                        raise
            
            # 保存文档
            try:
                doc.save(output_path)
                doc.close()
                return True
            except Exception as save_e:
                print(f"保存PDF文档时出错: {save_e}, 类型: {type(save_e)}")
                raise
                
        except Exception as e:
            import traceback
            print(f"保存可视化PDF失败: {e}, 类型: {type(e)}")
            print("详细错误信息:")
            traceback.print_exc()
            return False
    
    def save_to_json(self, output_path: Union[str, Path]) -> bool:
        """将版面分析结果保存为JSON文件
        
        Args:
            output_path: JSON输出路径
            
        Returns:
            bool: 保存是否成功
        """
        try:
            result_dict = {
                "pdf_path": self.pdf_path,
                "total_pages": self.total_pages,
                "pages": []
            }
            
            # 处理每一页
            for page_result in self.page_results:
                page_dict = {
                    "page_idx": page_result.page_idx,  # 页码从0开始
                    "blocks": []
                }
                
                # 处理页面中的每一个块
                for block in page_result.blocks:
                    block_dict = {
                        "class_name": block.class_name,
                        "bbox": block.box.tolist(),  # 将numpy数组转换为列表
                        "score": float(block.score),
                        "page_idx": block.page_idx,  # 页码从0开始
                        "block_idx": block.block_idx
                    }
                    page_dict["blocks"].append(block_dict)
                
                result_dict["pages"].append(page_dict)
            
            # 保存为JSON文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=2)
            
            return True
        
        except Exception as e:
            print(f"保存JSON失败: {e}")
            return False


class LayoutAnalyzer:
    """版面分析器"""
    
    def __init__(
        self,
        model_type: str = "doclayout_docstructbench",  # 使用的模型类型
        conf_thres: float = 0.25,  # 置信度阈值
        iou_thres: float = 0.5,  # IOU阈值
        use_cuda: bool = False  # 是否使用CUDA
    ):
        """
        初始化版面分析器
        
        Args:
            model_type: 模型类型，可选值见RapidLayout文档
            conf_thres: 置信度阈值
            iou_thres: IOU阈值
            use_cuda: 是否使用GPU加速
        """
        self.model_type = model_type
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.use_cuda = use_cuda
        
        # 初始化布局分析引擎
        self.layout_engine = RapidLayout(
            model_type=model_type,
            conf_thres=conf_thres,
            iou_thres=iou_thres,
            use_cuda=use_cuda
        )
    
    def analyze_pdf(
        self, 
        pdf_path: Union[str, Path], 
        page_range: Optional[Tuple[int, int]] = None,
        dpi: int = 200
    ) -> PDFLayoutResult:
        """
        分析PDF文档的版面
        
        Args:
            pdf_path: PDF文件路径
            page_range: 页面范围，如(0, 5)表示分析前5页，默认为None表示分析所有页面
            dpi: 转换为图像的DPI，默认200
        
        Returns:
            PDFLayoutResult: PDF版面分析结果
        """
        pdf_path = str(pdf_path)
        
        # 打开PDF文件
        pdf_document = fitz.open(pdf_path)
        total_pages = len(pdf_document)
        
        # 确定要处理的页面范围
        start_page = 0
        end_page = total_pages
        
        if page_range is not None:
            start_page = max(0, page_range[0])
            end_page = min(total_pages, page_range[1])
        
        # 创建结果对象
        pdf_result = PDFLayoutResult(
            pdf_path=pdf_path,
            total_pages=total_pages,
            page_results=[]
        )
        
        # 处理每一页
        for page_idx in range(start_page, end_page):
            # 将PDF页面转换为图像
            page = pdf_document.load_page(page_idx)
            pix = page.get_pixmap(dpi=dpi)
            
            # 转换为OpenCV格式
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            
            # 如果是RGBA格式，转换为BGR格式
            if pix.n == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            elif pix.n == 1:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            
            # 对图像进行版面分析
            boxes, scores, class_names, _ = self.layout_engine(img_array)
            
            # 创建版面块列表
            blocks = []
            for i, (box, score, class_name) in enumerate(zip(boxes, scores, class_names)):
                blocks.append(LayoutBlock(
                    class_name=class_name,
                    box=box,
                    score=score,
                    page_idx=page_idx,
                    block_idx=i
                ))
            
            # 添加到页面结果
            pdf_result.page_results.append(PageLayoutResult(
                page_idx=page_idx,
                img=img_array,
                blocks=blocks
            ))
        
        # 关闭PDF文档
        pdf_document.close()
        
        return pdf_result
    
    def analyze_image(
        self,
        img_path: Union[str, Path, np.ndarray]
    ) -> PageLayoutResult:
        """
        分析单个图像的版面
        
        Args:
            img_path: 图像路径或图像数组
            
        Returns:
            PageLayoutResult: 页面版面分析结果
        """
        # 如果输入是路径，读取图像
        if not isinstance(img_path, np.ndarray):
            img = cv2.imread(str(img_path))
        else:
            img = img_path
            
        # 对图像进行版面分析
        boxes, scores, class_names, _ = self.layout_engine(img)
        
        # 创建版面块列表
        blocks = []
        for i, (box, score, class_name) in enumerate(zip(boxes, scores, class_names)):
            blocks.append(LayoutBlock(
                class_name=class_name,
                box=box,
                score=score,
                page_idx=0,  # 单图像，设置页码为0
                block_idx=i
            ))
        
        # 返回页面结果
        return PageLayoutResult(
            page_idx=0,  # 单图像，设置页码为0
            img=img,
            blocks=blocks
        )
    
    def visualize_result(
        self,
        result: Union[PageLayoutResult, PDFLayoutResult],
        output_dir: Union[str, Path],
        prefix: str = "layout_",
        save_pdf: bool = False
    ) -> List[str]:
        """
        可视化版面分析结果
        
        Args:
            result: 页面或PDF的版面分析结果
            output_dir: 输出目录
            prefix: 输出文件名前缀
            save_pdf: 是否保存为PDF格式（仅当result为PDFLayoutResult时有效）
            
        Returns:
            List[str]: 保存的文件路径列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_paths = []
        
        if isinstance(result, PDFLayoutResult):
            # 如果是PDF结果，保存每一页
            for page_result in result.page_results:
                output_path = output_dir / f"{prefix}page_{page_result.page_idx}.png"
                
                vis_img = VisLayout.draw_detections(
                    page_result.img,
                    np.array([block.box for block in page_result.blocks]),
                    np.array([block.score for block in page_result.blocks]),
                    [block.class_name for block in page_result.blocks]
                )
                
                if vis_img is not None:
                    cv2.imwrite(str(output_path), vis_img)
                    saved_paths.append(str(output_path))
            
            # 如果需要，保存为PDF
            if save_pdf:
                pdf_path = output_dir / f"{prefix}result.pdf"
                if result.save_visualized_pdf(str(pdf_path)):
                    saved_paths.append(str(pdf_path))
        
        elif isinstance(result, PageLayoutResult):
            # 如果是单页结果
            output_path = output_dir / f"{prefix}result.png"
            
            vis_img = VisLayout.draw_detections(
                result.img,
                np.array([block.box for block in result.blocks]),
                np.array([block.score for block in result.blocks]),
                [block.class_name for block in result.blocks]
            )
            
            if vis_img is not None:
                cv2.imwrite(str(output_path), vis_img)
                saved_paths.append(str(output_path))
        
        return saved_paths