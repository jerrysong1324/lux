#  Copyright 2019-2020 The Lux Authors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import lux
import pandas as pd
from typing import Callable
from lux.vislib.altair.BarChart import BarChart
from lux.vislib.altair.ScatterChart import ScatterChart
from lux.vislib.altair.LineChart import LineChart
from lux.vislib.altair.Histogram import Histogram
from lux.vislib.altair.Heatmap import Heatmap
from lux.vislib.altair.Choropleth import Choropleth


class AltairRenderer:
    """
    Renderer for Charts based on Altair (https://altair-viz.github.io/)
    """

    def __init__(self, output_type="VegaLite"):
        self.output_type = output_type

    def __repr__(self):
        return f"AltairRenderer"

    def create_vis(self, vis, standalone=True):
        """
        Input Vis object and return a visualization specification

        Parameters
        ----------
        vis: lux.vis.Vis
                Input Vis (with data)
        standalone: bool
                Flag to determine if outputted code uses user-defined variable names or can be run independently
        Returns
        -------
        chart : altair.Chart
                Output Altair Chart Object
        """
        # Lazy Evaluation for 2D Binning
        if vis.mark == "scatter" and vis._postbin:
            vis._mark = "heatmap"
            from lux.executor.PandasExecutor import PandasExecutor

            PandasExecutor.execute_2D_binning(vis)
        # If a column has a Period dtype, or contains Period objects, convert it back to Datetime
        if vis.data is not None:
            for attr in list(vis.data.columns):
                if pd.api.types.is_period_dtype(vis.data.dtypes[attr]) or isinstance(
                    vis.data[attr].iloc[0], pd.Period
                ):
                    dateColumn = vis.data[attr]
                    vis.data[attr] = pd.PeriodIndex(dateColumn.values).to_timestamp()
                if pd.api.types.is_interval_dtype(vis.data.dtypes[attr]) or isinstance(
                    vis.data[attr].iloc[0], pd.Interval
                ):
                    vis.data[attr] = vis.data[attr].astype(str)
                if isinstance(attr, str):
                    if "." in attr:
                        attr_clause = vis.get_attr_by_attr_name(attr)[0]
                        # Suppress special character ".", not displayable in Altair
                        # attr_clause.attribute = attr_clause.attribute.replace(".", "")
                        vis._vis_data = vis.data.rename(columns={attr: attr.replace(".", "")})
        if vis.mark == "histogram":
            chart = Histogram(vis)
        elif vis.mark == "bar":
            chart = BarChart(vis)
        elif vis.mark == "scatter":
            chart = ScatterChart(vis)
        elif vis.mark == "line":
            chart = LineChart(vis)
        elif vis.mark == "heatmap":
            chart = Heatmap(vis)
        elif vis.mark == "geographical":
            chart = Choropleth(vis)
        else:
            chart = None

        if chart:
            if lux.config.plotting_style and (
                lux.config.plotting_backend == "vegalite" or lux.config.plotting_backend == "altair"
            ):
                chart.chart = lux.config.plotting_style(chart.chart)
            if self.output_type == "VegaLite":
                chart_dict = chart.chart.to_dict()
                # this is a bit of a work around because altair must take a pandas dataframe and we can only generate a luxDataFrame
                # chart["data"] =  { "values": vis.data.to_dict(orient='records') }
                # chart_dict["width"] = 160
                # chart_dict["height"] = 150
                chart_dict["vislib"] = "vegalite"
                return chart_dict
            elif self.output_type == "Altair":
                import inspect

                source = ""
                if lux.config.plotting_style:
                    if "def custom_config(chart):" in lux.config.plotting_style_code:
                        source = lux.config.plotting_style_code
                    else:
                        source = inspect.getsource(lux.config.plotting_style)
                    default_vis_style_code = "# Default Lux Style \nchart = chart.configure_title(fontWeight=500,fontSize=13,font='Helvetica Neue')\n"
                    default_vis_style_code += "chart = chart.configure_axis(titleFontWeight=500,titleFontSize=11,titleFont='Helvetica Neue',\n"
                    default_vis_style_code += "\t\t\t\t\tlabelFontWeight=400,labelFontSize=9,labelFont='Helvetica Neue',labelColor='#505050')\n"
                    default_vis_style_code += "chart = chart.configure_legend(titleFontWeight=500,titleFontSize=10,titleFont='Helvetica Neue',\n"
                    default_vis_style_code += (
                        "\t\t\t\t\tlabelFontWeight=400,labelFontSize=9,labelFont='Helvetica Neue')\n"
                    )
                    default_vis_style_code += "chart = chart.properties(width=160,height=150)\n"
                    vis_style_code = "\n# Custom Style Additions"
                    # TODO: improve parsing such that it splits based on line of logic instead of line of code
                    for line in source.split("\n    ")[1:-1]:
                        if line.strip() not in default_vis_style_code:
                            vis_style_code += "\n" + line
                    if vis_style_code == "\n# Custom Style Additions":
                        vis_style_code = default_vis_style_code
                    else:
                        vis_style_code = default_vis_style_code + vis_style_code
                    vis_style_code = vis_style_code.replace("\n\t\t", "\n")
                    vis_style_code = vis_style_code.replace("\n        ", "\n")
                    lux.config.plotting_style_code = vis_style_code
                chart.code = chart.code.replace("\n\t\t", "\n")
                chart.code = chart.code.replace("\n        ", "\n")

                var = vis._source
                if var is not None:
                    all_vars = []
                    for f_info in inspect.getouterframes(inspect.currentframe()):
                        local_vars = f_info.frame.f_back
                        if local_vars:
                            callers_local_vars = local_vars.f_locals.items()
                            possible_vars = [
                                var_name for var_name, var_val in callers_local_vars if var_val is var
                            ]
                            all_vars.extend(possible_vars)
                    found_variable = [
                        possible_var for possible_var in all_vars if possible_var[0] != "_"
                    ][0]
                else:  # if vis._source was not set when the Vis was created
                    found_variable = "df"
                if standalone:
                    chart.code = chart.code.replace(
                        "placeholder_variable",
                        f"pd.DataFrame({str(vis.data.to_dict())})",
                    )
                else:
                    # TODO: Placeholder (need to read dynamically via locals())
                    chart.code = chart.code.replace("placeholder_variable", found_variable)
                return chart.code
