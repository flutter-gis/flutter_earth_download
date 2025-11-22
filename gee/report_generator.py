"""
PDF Report Generator for Mosaic Processing Results
Generates comprehensive reports with statistics, visualizations, and gap-filling details.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict

# reportlab is required for PDF report generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.pdfgen import canvas
REPORTLAB_AVAILABLE = True

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_pdf import PdfPages
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("matplotlib not available - visualizations will be limited")


class MosaicReportGenerator:
    """Generate comprehensive PDF reports for mosaic processing."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.stats = {
            "tiles": [],
            "total_tiles": 0,
            "complete_tiles": 0,
            "failed_tiles": 0,
            "partial_tiles": 0,
            "satellite_usage": defaultdict(int),
            "satellite_dominance": defaultdict(int),
            "quality_scores": [],
            "gap_filling": {
                "total_gaps_identified": 0,
                "total_gaps_filled": 0,
                "total_gaps_unfillable": 0,
                "total_attempts": 0,
                "total_images_added": 0,
                "unfillable_details": []
            },
            "processing_time": 0.0,
            "date_range": None,
            "bbox": None,
            "resolution": None,
            "errors": [],
            "warnings": []
        }
    
    def add_tile_result(self, tile_idx: int, provenance: Dict, processing_time: float = 0.0):
        """Add a tile's processing results to the statistics."""
        tile_stat = {
            "tile_idx": tile_idx,
            "status": provenance.get("status", "unknown"),
            "dominant_satellite": provenance.get("dominant_satellite"),
            "method": provenance.get("method"),
            "detailed_stats": provenance.get("detailed_stats"),
            "gap_filling_stats": provenance.get("gap_filling_stats", {}),
            "processing_time": processing_time,
            "error": None
        }
        
        # Determine tile status
        gap_stats = provenance.get("gap_filling_stats", {})
        final_coverage = gap_stats.get("final_coverage", 0.0)
        
        if provenance.get("status") == "complete":
            self.stats["complete_tiles"] += 1
            if final_coverage < 0.95:
                self.stats["partial_tiles"] += 1
                tile_stat["coverage"] = final_coverage
        elif provenance.get("status") in ["failed", "no_imagery", "missing_bands"]:
            self.stats["failed_tiles"] += 1
            tile_stat["error"] = provenance.get("status")
        else:
            # Check coverage to determine if partial
            if final_coverage < 0.95 and final_coverage > 0.0:
                self.stats["partial_tiles"] += 1
                tile_stat["coverage"] = final_coverage
            else:
                self.stats["complete_tiles"] += 1
        
        # Track satellite usage
        if tile_stat["dominant_satellite"]:
            self.stats["satellite_dominance"][tile_stat["dominant_satellite"]] += 1
        
        # Track quality scores
        if tile_stat["detailed_stats"]:
            quality = tile_stat["detailed_stats"].get("quality_score")
            if quality is not None:
                self.stats["quality_scores"].append(quality)
                satellite = tile_stat["detailed_stats"].get("satellite")
                if satellite:
                    self.stats["satellite_usage"][satellite] += 1
        
        # Track gap-filling statistics
        if gap_stats:
            self.stats["gap_filling"]["total_gaps_identified"] += gap_stats.get("gaps_identified", 0)
            self.stats["gap_filling"]["total_gaps_filled"] += gap_stats.get("gaps_filled", 0)
            self.stats["gap_filling"]["total_gaps_unfillable"] += gap_stats.get("gaps_unfillable", 0)
            self.stats["gap_filling"]["total_attempts"] += gap_stats.get("gap_filling_attempts", 0)
            self.stats["gap_filling"]["total_images_added"] += gap_stats.get("images_added_for_gaps", 0)
            
            unfillable = gap_stats.get("unfillable_gap_details", [])
            if unfillable:
                self.stats["gap_filling"]["unfillable_details"].extend(unfillable)
        
        self.stats["tiles"].append(tile_stat)
        self.stats["total_tiles"] += 1
    
    def set_metadata(self, date_range: Tuple[str, str], bbox: Tuple[float, float, float, float], 
                     resolution: float, processing_time: float = 0.0):
        """Set processing metadata."""
        self.stats["date_range"] = date_range
        self.stats["bbox"] = bbox
        self.stats["resolution"] = resolution
        self.stats["processing_time"] = processing_time
    
    def add_error(self, error_msg: str):
        """Add an error message."""
        self.stats["errors"].append(error_msg)
    
    def add_warning(self, warning_msg: str):
        """Add a warning message."""
        self.stats["warnings"].append(warning_msg)
    
    def generate_report(self, output_filename: str = "mosaic_processing_report.pdf"):
        """Generate the PDF report."""
        # reportlab is required - if we get here, it should be available
        if not REPORTLAB_AVAILABLE:
            logging.error("reportlab not available - this should not happen as it is a required dependency")
            raise ImportError("reportlab is required for PDF report generation. Install with: pip install reportlab")
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        try:
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=30,
            )
            story.append(Paragraph("Mosaic Processing Report", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Executive Summary
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            story.append(self._create_executive_summary(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Tile Status Summary
            story.append(PageBreak())
            story.append(Paragraph("Tile Status Summary", styles['Heading2']))
            story.append(self._create_tile_status_table(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Gap-Filling Statistics
            story.append(Paragraph("Gap-Filling Statistics", styles['Heading2']))
            story.append(self._create_gap_filling_section(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Satellite Usage Analysis
            story.append(PageBreak())
            story.append(Paragraph("Satellite Usage Analysis", styles['Heading2']))
            story.append(self._create_satellite_usage_section(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Quality Metrics
            story.append(Paragraph("Quality Metrics", styles['Heading2']))
            story.append(self._create_quality_metrics_section(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Coverage Analysis
            story.append(PageBreak())
            story.append(Paragraph("Coverage Analysis", styles['Heading2']))
            story.append(self._create_coverage_section(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Processing Details
            story.append(Paragraph("Processing Details", styles['Heading2']))
            story.append(self._create_processing_details_section(styles))
            story.append(Spacer(1, 0.3*inch))
            
            # Errors and Warnings
            if self.stats["errors"] or self.stats["warnings"]:
                story.append(PageBreak())
                story.append(Paragraph("Errors and Warnings", styles['Heading2']))
                story.append(self._create_errors_warnings_section(styles))
            
            # Build PDF
            doc.build(story)
            logging.info(f"PDF report generated: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error generating PDF report: {e}")
            return None
    
    def _create_executive_summary(self, styles):
        """Create executive summary section."""
        total = self.stats["total_tiles"]
        complete = self.stats["complete_tiles"]
        failed = self.stats["failed_tiles"]
        partial = self.stats["partial_tiles"]
        success_rate = (complete / total * 100) if total > 0 else 0.0
        
        # Calculate overall coverage
        coverage_values = []
        for tile in self.stats["tiles"]:
            gap_stats = tile.get("gap_filling_stats", {})
            final_cov = gap_stats.get("final_coverage")
            if final_cov is not None:
                coverage_values.append(final_cov)
        overall_coverage = sum(coverage_values) / len(coverage_values) * 100 if coverage_values else 0.0
        
        gap_stats = self.stats["gap_filling"]
        gap_fill_rate = (gap_stats["total_gaps_filled"] / gap_stats["total_gaps_identified"] * 100) if gap_stats["total_gaps_identified"] > 0 else 0.0
        
        data = [
            ["Metric", "Value"],
            ["Total Tiles Processed", str(total)],
            ["Complete Tiles", f"{complete} ({success_rate:.1f}%)"],
            ["Failed Tiles", str(failed)],
            ["Partial Tiles", str(partial)],
            ["Overall Coverage", f"{overall_coverage:.1f}%"],
            ["Gap-Filling Success Rate", f"{gap_fill_rate:.1f}%"],
            ["Processing Time", f"{self.stats['processing_time']:.1f} seconds"],
        ]
        
        if self.stats["date_range"]:
            data.append(["Date Range", f"{self.stats['date_range'][0]} to {self.stats['date_range'][1]}"])
        
        table = Table(data, colWidths=[3*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        return table
    
    def _create_tile_status_table(self, styles):
        """Create tile status summary table."""
        data = [["Tile ID", "Status", "Coverage %", "Dominant Satellite", "Images Used"]]
        
        for tile in sorted(self.stats["tiles"], key=lambda x: x["tile_idx"]):
            tile_idx = tile["tile_idx"]
            status = tile.get("status", "unknown")
            gap_stats = tile.get("gap_filling_stats", {})
            coverage = gap_stats.get("final_coverage", 0.0) * 100
            dominant = tile.get("dominant_satellite", "N/A")
            images_used = gap_stats.get("images_added_for_gaps", 0) + 1  # +1 for initial best image
            
            data.append([
                f"Tile {tile_idx:04d}",
                status,
                f"{coverage:.1f}%" if coverage > 0 else "N/A",
                dominant or "N/A",
                str(images_used)
            ])
        
        table = Table(data, colWidths=[1*inch, 1.2*inch, 1*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        return table
    
    def _create_gap_filling_section(self, styles):
        """Create gap-filling statistics section."""
        gap_stats = self.stats["gap_filling"]
        
        story = []
        
        # Summary table
        data = [
            ["Metric", "Value"],
            ["Total Gaps Identified", str(gap_stats["total_gaps_identified"])],
            ["Gaps Successfully Filled", str(gap_stats["total_gaps_filled"])],
            ["Unfillable Gaps", str(gap_stats["total_gaps_unfillable"])],
            ["Gap-Filling Attempts", str(gap_stats["total_attempts"])],
            ["Images Added for Gap-Filling", str(gap_stats["total_images_added"])],
        ]
        
        fill_rate = (gap_stats["total_gaps_filled"] / gap_stats["total_gaps_identified"] * 100) if gap_stats["total_gaps_identified"] > 0 else 0.0
        data.append(["Gap-Filling Success Rate", f"{fill_rate:.1f}%"])
        
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        
        # Unfillable gaps details
        if gap_stats["unfillable_details"]:
            story.append(Paragraph("Unfillable Gap Details", styles['Heading3']))
            unfillable_data = [["Tile ID", "Iteration", "Coverage %", "Reason"]]
            for detail in gap_stats["unfillable_details"][:20]:  # Limit to first 20
                unfillable_data.append([
                    f"Tile {detail.get('tile_idx', 'N/A'):04d}" if detail.get('tile_idx') is not None else "N/A",
                    str(detail.get("iteration", "N/A")),
                    f"{detail.get('coverage', 0.0) * 100:.1f}%",
                    detail.get("reason", "Unknown")
                ])
            
            unfillable_table = Table(unfillable_data, colWidths=[1*inch, 1*inch, 1*inch, 3*inch])
            unfillable_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(unfillable_table)
        
        return story
    
    def _create_satellite_usage_section(self, styles):
        """Create satellite usage analysis section."""
        story = []
        
        # Dominant satellite per tile
        dominance_data = [["Satellite", "Tiles Dominated", "Percentage"]]
        total_dominated = sum(self.stats["satellite_dominance"].values())
        for sat, count in sorted(self.stats["satellite_dominance"].items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_dominated * 100) if total_dominated > 0 else 0.0
            dominance_data.append([sat, str(count), f"{pct:.1f}%"])
        
        dominance_table = Table(dominance_data, colWidths=[2.5*inch, 2*inch, 2*inch])
        dominance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(Paragraph("Satellite Dominance (per tile)", styles['Heading3']))
        story.append(dominance_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Overall satellite usage
        usage_data = [["Satellite", "Images Used"]]
        for sat, count in sorted(self.stats["satellite_usage"].items(), key=lambda x: x[1], reverse=True):
            usage_data.append([sat, str(count)])
        
        usage_table = Table(usage_data, colWidths=[2.5*inch, 2*inch])
        usage_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(Paragraph("Overall Satellite Usage", styles['Heading3']))
        story.append(usage_table)
        
        return story
    
    def _create_quality_metrics_section(self, styles):
        """Create quality metrics section."""
        story = []
        
        if not self.stats["quality_scores"]:
            story.append(Paragraph("No quality score data available.", styles['Normal']))
            return story
        
        scores = self.stats["quality_scores"]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        
        data = [
            ["Metric", "Value"],
            ["Average Quality Score", f"{avg_score:.3f}"],
            ["Minimum Quality Score", f"{min_score:.3f}"],
            ["Maximum Quality Score", f"{max_score:.3f}"],
            ["Total Images Scored", str(len(scores))],
        ]
        
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        
        return story
    
    def _create_coverage_section(self, styles):
        """Create coverage analysis section."""
        story = []
        
        coverage_values = []
        for tile in self.stats["tiles"]:
            gap_stats = tile.get("gap_filling_stats", {})
            final_cov = gap_stats.get("final_coverage")
            if final_cov is not None:
                coverage_values.append(final_cov * 100)
        
        if not coverage_values:
            story.append(Paragraph("No coverage data available.", styles['Normal']))
            return story
        
        avg_coverage = sum(coverage_values) / len(coverage_values)
        min_coverage = min(coverage_values)
        max_coverage = max(coverage_values)
        
        # Count tiles by coverage ranges
        excellent = sum(1 for c in coverage_values if c >= 99.0)
        good = sum(1 for c in coverage_values if 95.0 <= c < 99.0)
        fair = sum(1 for c in coverage_values if 80.0 <= c < 95.0)
        poor = sum(1 for c in coverage_values if c < 80.0)
        
        data = [
            ["Metric", "Value"],
            ["Average Coverage", f"{avg_coverage:.1f}%"],
            ["Minimum Coverage", f"{min_coverage:.1f}%"],
            ["Maximum Coverage", f"{max_coverage:.1f}%"],
            ["Tiles with ≥99% Coverage", str(excellent)],
            ["Tiles with 95-99% Coverage", str(good)],
            ["Tiles with 80-95% Coverage", str(fair)],
            ["Tiles with <80% Coverage", str(poor)],
        ]
        
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        
        return story
    
    def _create_processing_details_section(self, styles):
        """Create processing details section."""
        story = []
        
        data = []
        if self.stats["date_range"]:
            data.append(["Date Range", f"{self.stats['date_range'][0]} to {self.stats['date_range'][1]}"])
        if self.stats["bbox"]:
            bbox = self.stats["bbox"]
            data.append(["Bounding Box", f"({bbox[0]:.4f}, {bbox[1]:.4f}) to ({bbox[2]:.4f}, {bbox[3]:.4f})"])
        if self.stats["resolution"]:
            data.append(["Target Resolution", f"{self.stats['resolution']} meters"])
        data.append(["Processing Time", f"{self.stats['processing_time']:.1f} seconds"])
        data.append(["Total Tiles", str(self.stats["total_tiles"])])
        
        # Count total images tested and used
        total_images_tested = sum(len(tile.get("all_test_results", [])) for tile in self.stats["tiles"])
        total_images_used = sum(
            tile.get("gap_filling_stats", {}).get("images_added_for_gaps", 0) + 1
            for tile in self.stats["tiles"]
            if tile.get("status") == "complete"
        )
        data.append(["Total Images Tested", str(total_images_tested)])
        data.append(["Total Images Used", str(total_images_used)])
        
        if not data:
            story.append(Paragraph("No processing details available.", styles['Normal']))
            return story
        
        table = Table(data, colWidths=[3*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        
        return story
    
    def _create_errors_warnings_section(self, styles):
        """Create errors and warnings section."""
        story = []
        
        if self.stats["errors"]:
            story.append(Paragraph("Errors", styles['Heading3']))
            for error in self.stats["errors"][:20]:  # Limit to first 20
                story.append(Paragraph(f"• {error}", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
        
        if self.stats["warnings"]:
            story.append(Paragraph("Warnings", styles['Heading3']))
            for warning in self.stats["warnings"][:20]:  # Limit to first 20
                story.append(Paragraph(f"• {warning}", styles['Normal']))
        
        return story

