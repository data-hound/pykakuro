def draw_kakuro_svg():
  import svgfig

  x_size = 8
  y_size = 9

  puzzle = (0,0,0,0,0,0,(0,16),(0,3),
          0,0,0,0,0,(8,6),1,1,
          0,(0,16),(0,6),0,(14,30),1,1,1,
          (11,0),1,1,(7,0),1,1,(0,6),0,
          (10,0),1,1,(13,7),1,1,1,(0,16),
          0,(14,0),1,1,1,(8,0),1,1,
          0,(0,4),(9,17),1,1,(11,0),1,1,
          (12,0),1,1,1,0,0,0,0,
          (10,0),1,1,0,0,0,0,0
         )
  cells = []

  CELL_WIDTH = 20
  CELL_HEIGHT = 20

  def draw_cell(cell_data):
    out = []

    if cell_data == 0:
      out.append(svgfig.Rect(0, 0, CELL_WIDTH, CELL_HEIGHT, fill="black"))
    elif type(cell_data) == type(1):
      out.append(svgfig.Rect(0, 0, CELL_WIDTH, CELL_HEIGHT))
      out.append(svgfig.Text(10, 10, cell_data,
                             text_anchor="middle",
                             font_size=12,
                             font_weight=600,
                             dominant_baseline="middle",
                             fill="brown",
                            ))
    elif type(cell_data) == type(()):
      across = cell_data[0]
      down = cell_data[1]
      out.append(svgfig.Rect(0, 0, CELL_WIDTH, CELL_HEIGHT))
      out.append(svgfig.Line(0, 0, CELL_WIDTH, CELL_HEIGHT,
                             stroke_width=1,
                            ))
      if down == 0:
        points = ((0,0),(0,CELL_HEIGHT),(CELL_WIDTH,CELL_HEIGHT))
        out.append(svgfig.Poly(points, "lines", fill="black"))
      else:
        out.append(svgfig.Text(2, 18, down,
                               text_anchor="start",
                               font_size=7,
                               alignment_baseline="middle",
                              ))
      if across == 0:
        points = ((0,0),(CELL_WIDTH,0),(CELL_WIDTH,CELL_HEIGHT))
        out.append(svgfig.Poly(points, "lines", fill="black"))
      else:
        out.append(svgfig.Text(19, 7, across,
                               text_anchor="end",
                               font_size=7,
                              ))
    else:
      raise Exception("")
    return out

  def cell(x, y, cell_data):

    def t(xi,yi):
      return 1+xi+x*(CELL_WIDTH), 1+yi+y*(CELL_HEIGHT)

    fig = svgfig.Fig(
      *draw_cell(cell_data),
      trans=t)
    return fig.SVG()


  for y in range(y_size):
    for x in range(x_size):
      cells.append(cell(x, y, puzzle[y*x_size+x]))

  g = svgfig.SVG("g", *cells)

  c = svgfig.canvas(g,
                    width="400px",
                    height="400px",
                    font_family='Arial Black',
                    viewBox="0 0 %d %d" % (x_size * CELL_WIDTH + 2, y_size * CELL_HEIGHT + 2))

  c.save('tmp.svg')

draw_kakuro_svg()
