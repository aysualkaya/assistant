# app/visualization/visualizer.py - IMPROVED VERSION
"""
Enhanced Visualization with Auto-Recommendation
"""

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Optional, Literal
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Visualizer:
    """Enhanced visualizer with auto chart type selection"""
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize visualizer
        
        Args:
            output_dir: Directory to save charts (optional)
        """
        self.output_dir = Path(output_dir) if output_dir else Path("data/charts")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def recommend_chart_type(self, df: pd.DataFrame, x: str, y: str) -> str:
        """
        Recommend best chart type based on data
        
        Args:
            df: DataFrame
            x: X column
            y: Y column
            
        Returns:
            Recommended chart type
        """
        row_count = len(df)
        
        # Check if x is temporal
        is_temporal = pd.api.types.is_datetime64_any_dtype(df[x]) or \
                     'date' in x.lower() or 'month' in x.lower() or 'year' in x.lower()
        
        # Recommendation logic
        if is_temporal:
            return "line"  # Time series → line chart
        elif row_count <= 10:
            return "bar"   # Few categories → bar chart
        elif row_count <= 20:
            return "barh"  # Many categories → horizontal bar
        else:
            return "bar"   # Default
    
    def plot_matplotlib(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        chart_type: Optional[str] = None,
        save: bool = False,
        show: bool = True
    ):
        """
        Create matplotlib chart with auto-recommendation
        
        Args:
            df: DataFrame
            x: X column
            y: Y column
            title: Chart title
            chart_type: Chart type (auto if None)
            save: Save to file
            show: Show chart (set False for Streamlit)
        """
        try:
            # Auto-recommend chart type
            if chart_type is None:
                chart_type = self.recommend_chart_type(df, x, y)
            
            logger.info(f"Creating {chart_type} chart: {title}")
            
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Plot based on type
            if chart_type == "line":
                df.plot(x=x, y=y, kind="line", ax=ax, marker='o')
            elif chart_type == "bar":
                df.plot(x=x, y=y, kind="bar", ax=ax)
            elif chart_type == "barh":
                df.plot(x=x, y=y, kind="barh", ax=ax)
            else:
                df.plot(x=x, y=y, kind="bar", ax=ax)
            
            # Styling
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel(x, fontsize=11)
            ax.set_ylabel(y, fontsize=11)
            ax.grid(True, alpha=0.3)
            
            # Rotate x labels if many
            if len(df) > 10:
                plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            
            # Save if requested
            if save:
                filename = self.output_dir / f"{title.replace(' ', '_')}.png"
                plt.savefig(filename, dpi=150, bbox_inches='tight')
                logger.info(f"Chart saved to: {filename}")
            
            # Show if requested (disable for Streamlit)
            if show:
                plt.show()
            else:
                return fig  # Return figure for Streamlit
            
            plt.close()
            
        except Exception as e:
            logger.error(f"Matplotlib plot error: {e}")
            if show:
                plt.close()
    
    def plot_plotly(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        chart_type: Optional[str] = None,
        save: bool = False
    ):
        """
        Create interactive Plotly chart
        
        Args:
            df: DataFrame
            x: X column
            y: Y column
            title: Chart title
            chart_type: Chart type (auto if None)
            save: Save to HTML
        """
        try:
            # Auto-recommend chart type
            if chart_type is None:
                chart_type = self.recommend_chart_type(df, x, y)
            
            logger.info(f"Creating interactive {chart_type} chart: {title}")
            
            # Create chart based on type
            if chart_type == "line":
                fig = px.line(df, x=x, y=y, title=title, markers=True)
            elif chart_type == "bar":
                fig = px.bar(df, x=x, y=y, title=title)
            elif chart_type == "barh":
                fig = px.bar(df, x=y, y=x, title=title, orientation='h')
            else:
                fig = px.bar(df, x=x, y=y, title=title)
            
            # Update layout
            fig.update_layout(
                title_font_size=16,
                showlegend=False,
                hovermode='x unified'
            )
            
            # Save if requested
            if save:
                filename = self.output_dir / f"{title.replace(' ', '_')}.html"
                fig.write_html(filename)
                logger.info(f"Interactive chart saved to: {filename}")
            
            fig.show()
            
        except Exception as e:
            logger.error(f"Plotly plot error: {e}")
    
    def plot_comparison(
        self,
        df: pd.DataFrame,
        category_col: str,
        value_col: str,
        title: str = "Comparison"
    ):
        """
        Create comparison chart (optimized for 2-3 categories)
        
        Args:
            df: DataFrame with 2-3 rows
            category_col: Category column
            value_col: Value column
            title: Chart title
        """
        try:
            fig = go.Figure(data=[
                go.Bar(
                    x=df[category_col],
                    y=df[value_col],
                    text=df[value_col].apply(lambda x: f"{x:,.0f}"),
                    textposition='auto',
                )
            ])
            
            fig.update_layout(
                title=title,
                title_font_size=16,
                showlegend=False,
                yaxis_title=value_col,
                xaxis_title=category_col
            )
            
            fig.show()
            
        except Exception as e:
            logger.error(f"Comparison plot error: {e}")


# Singleton instance
_visualizer_instance = None

def get_visualizer() -> Visualizer:
    """Get singleton visualizer instance"""
    global _visualizer_instance
    if _visualizer_instance is None:
        _visualizer_instance = Visualizer()
    return _visualizer_instance