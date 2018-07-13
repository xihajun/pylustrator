import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.axes._subplots import Axes
from matplotlib.patches import Rectangle, Ellipse
from matplotlib.text import Text
import matplotlib as mpl

DIR_X0 = 1
DIR_Y0 = 2
DIR_X1 = 4
DIR_Y1 = 8


class TargetWrapper(object):
    target = None

    def __init__(self, target):
        self.target = target
        self.figure = target.figure
        self.do_scale = True
        self.fixed_aspect = False
        if isinstance(self.target, mpl.patches.Patch):
            self.get_transform = self.target.get_data_transform
        elif isinstance(self.target, Axes):
            if self.target.get_aspect() != "auto" and self.target.get_adjustable() != "datalim":
                self.fixed_aspect = True
            self.get_transform = lambda: self.target.figure.transFigure
        else:
            self.get_transform = self.target.get_transform
            self.do_scale = False

    def get_positions(self):
        points = []
        if isinstance(self.target, Rectangle):
            points.append(self.target.get_xy())
            p2 = (self.target.get_x() + self.target.get_width(), self.target.get_y() + self.target.get_height())
            points.append(p2)
        elif isinstance(self.target, Ellipse):
            c = self.target.center
            w = self.target.width
            h = self.target.height
            points.append((c[0]-w/2, c[1]-h/2))
            points.append((c[0]+w/2, c[1]+h/2))
        elif isinstance(self.target, Text):
            points.append(self.target.get_position())
            bbox = self.target.get_bbox_patch()
            if bbox:
                points.append(bbox.get_transform().transform((bbox.get_x(), bbox.get_y())))
                points.append(bbox.get_transform().transform((bbox.get_x()+bbox.get_width(), bbox.get_y()+bbox.get_height())))
            points[1:] = self.transform_inverted_points(points[1:])
        elif isinstance(self.target, Axes):
            p1, p2 = np.array(self.target.get_position())
            points.append(p1)
            points.append(p2)
        return self.transform_points(points)

    def set_positions(self, points):
        points = self.transform_inverted_points(points)

        if isinstance(self.target, Rectangle):
            self.target.set_xy(points[0])
            self.target.set_width(points[1][0] - points[0][0])
            self.target.set_height(points[1][1] - points[0][1])
            if self.target.get_label() is None or not self.target.get_label().startswith("_rect"):
                self.figure.change_tracker.addChange(self.target, ".set_xy([%f, %f])" % tuple(self.target.get_xy()))
                self.figure.change_tracker.addChange(self.target, ".set_width(%f)" % self.target.get_width())
                self.figure.change_tracker.addChange(self.target, ".set_height(%f)" % self.target.get_height())
        elif isinstance(self.target, Ellipse):
            self.target.center = np.mean(points, axis=0)
            self.target.width = points[1][0] - points[0][0]
            self.target.height = points[1][1] - points[0][1]
            self.figure.change_tracker.addChange(self.target, ".center = (%f, %f)" % tuple(self.target.center))
            self.figure.change_tracker.addChange(self.target, ".width = %f" % self.target.width)
            self.figure.change_tracker.addChange(self.target, ".height = %f" % self.target.height)
        elif isinstance(self.target, Text):
            self.target.set_position(points[0])
            self.figure.change_tracker.addChange(self.target, ".set_position([%f, %f])" % self.target.get_position())
        elif isinstance(self.target, Axes):
            position = np.array([points[0], points[1]-points[0]]).flatten()
            if self.fixed_aspect:
                position[3] = position[2]*self.target.get_position().height/self.target.get_position().width
            self.target.set_position(position)
            self.figure.change_tracker.addChange(self.target, ".set_position([%f, %f, %f, %f])" % tuple(np.array([points[0], points[1]-points[0]]).flatten()))

    def get_extent(self):
        points = np.array(self.get_positions())
        return [np.min(points[:, 0]),
                np.min(points[:, 1]),
                np.max(points[:, 0]),
                np.max(points[:, 1])]

    def transform_points(self, points):
        transform = self.get_transform()
        return [transform.transform(p) for p in points]

    def transform_inverted_points(self, points):
        transform = self.get_transform()
        return [transform.inverted().transform(p) for p in points]

class snapBase(Line2D):
    def __init__(self, ax_source, ax_target, edge):
        self.ax_source = TargetWrapper(ax_source)
        self.ax_target = TargetWrapper(ax_target)
        self.edge = edge
        Line2D.__init__(self, [], [], transform=None, clip_on=False, lw=1, zorder=100, linestyle="dashed",
                        color="r", marker="o", ms=1, label="_tmp_snap")
        plt.gca().add_artist(self)

    def getPosition(self, axes):
        try:
            return axes.get_extent()
        except AttributeError:
            return np.array(axes.figure.transFigure.transform(axes.get_position())).flatten()

    def getDistance(self, p1):
        pass

    def checkSnap(self, index):
        distance = self.getDistance(index)
        if abs(distance) < 10:
            return distance
        return None

    def checkSnapActive(self):
        distance = min([self.getDistance(index) for index in [0, 1]])
        if abs(distance) < 1:
            self.show()
        else:
            self.hide()

    def show(self):
        pass

    def hide(self):
        self.set_data((), ())

    def remove(self):
        self.hide()
        try:
            self.axes.artists.remove(self)
        except ValueError:
            pass


class snapSameEdge(snapBase):

    def getDistance(self, index):
        if self.edge % 2 != index:
            return np.inf
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        return p1[self.edge] - p2[self.edge]

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        if self.edge % 2 == 0:
            self.set_data((p1[self.edge], p1[self.edge], p2[self.edge], p2[self.edge]),
                          (p1[self.edge - 1], p1[self.edge + 1], p2[self.edge - 1], p2[self.edge + 1]))
        else:
            self.set_data((p1[self.edge - 1], p1[self.edge - 3], p2[self.edge - 1], p2[self.edge - 3]),
                          (p1[self.edge], p1[self.edge], p2[self.edge], p2[self.edge]))


class snapSameDimension(snapBase):
    def getDistance(self, index):
        if self.edge % 2 != index:
            return np.inf
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        return (p2[self.edge - 2] - p2[self.edge]) - (p1[self.edge - 2] - p1[self.edge])

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        if self.edge % 2 == 0:
            self.set_data((p1[0], p1[2], np.nan, p2[0], p2[2]),
                          (p1[1] * 0.5 + p1[3] * 0.5, p1[1] * 0.5 + p1[3] * 0.5, np.nan, p2[1] * 0.5 + p2[3] * 0.5,
                           p2[1] * 0.5 + p2[3] * 0.5))
        else:
            self.set_data((p1[0] * 0.5 + p1[2] * 0.5, p1[0] * 0.5 + p1[2] * 0.5, np.nan, p2[0] * 0.5 + p2[2] * 0.5,
                           p2[0] * 0.5 + p2[2] * 0.5),
                          (p1[1], p1[3], np.nan, p2[1], p2[3]))


class snapSamePos(snapBase):
    def getPosition(self, text):
        return np.array(text.get_transform().transform(text.target.get_position()))

    def getDistance(self, index):
        if self.edge % 2 != index:
            return np.inf
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        return p1[self.edge] - p2[self.edge]

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        self.set_data((p1[0], p2[0]), (p1[1], p2[1]))


class snapSameBorder(snapBase):
    def __init__(self, ax_source, ax_target, ax_target2, edge):
        snapBase.__init__(self, ax_source, ax_target, edge)
        self.ax_target2 = ax_target2

    def overlap(self, p1, p2, dir):
        if p1[dir + 2] < p2[dir] or p1[dir] > p2[dir + 2]:
            return False
        return True

    def getBorders(self, p1, p2):
        borders = []
        for edge in [0, 1]:
            if self.overlap(p1, p2, 1 - edge):
                if p1[edge + 2] < p2[edge]:
                    dist = p2[edge] - p1[edge + 2]
                    borders.append([edge * 2 + 0, dist])
                if p1[edge] > p2[edge + 2]:
                    dist = p1[edge] - p2[edge + 2]
                    borders.append([edge * 2 + 1, dist])
        return np.array(borders)

    def getDistance(self, index):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        p3 = self.getPosition(self.ax_target2)
        for edge in [index]:
            if not (self.edge & DIR_X1) and not (self.edge & DIR_Y1):
                if p1[edge + 2] < p2[edge]:
                    continue
            if not (self.edge & DIR_X0) and not (self.edge & DIR_Y0):
                if p1[edge] > p2[edge + 2]:
                    continue
            if (p1[edge + 2] < p2[edge] or p1[edge] > p2[edge + 2]) and self.overlap(p1, p2, 1 - edge):
                distances = np.array([p2[edge] - p1[edge + 2], p1[edge] - p2[edge + 2]])
                index1 = np.argmax(distances)
                distance = distances[index1]
                borders = self.getBorders(p2, p3)
                if len(borders):
                    deltas = distance - borders[:, 1]
                    index2 = np.argmin(np.abs(deltas))
                    self.dir2 = borders[index2, 0]
                    self.dir1 = edge * 2 + index1
                    return deltas[index2] * (-1 + 2 * index1)
        return np.inf

    def getConnection(self, p1, p2, dir):
        edge, order = dir // 2, dir % 2
        if order == 1:
            p1, p2 = p2, p1
        if edge == 0:
            y = np.mean([max(p1[1], p2[1]), min(p1[3], p2[3])])
            return [[p1[2], p2[0], np.nan], [y, y, np.nan]]
        x = np.mean([max(p1[0], p2[0]), min(p1[2], p2[2])])
        return [[x, x, np.nan], [p1[3], p2[1], np.nan]]

    def show(self):
        p1 = self.getPosition(self.ax_source)
        p2 = self.getPosition(self.ax_target)
        p3 = self.getPosition(self.ax_target2)
        x1, y1 = self.getConnection(p1, p2, self.dir1)
        x2, y2 = self.getConnection(p2, p3, self.dir2)
        x1.extend(x2)
        y1.extend(y2)
        self.set_data((x1, y1))


def checkSnaps(snaps):
    result = [0, 0]
    for index in range(2):
        best = np.inf
        for snap in snaps:
            delta = snap.checkSnap(index)
            if delta is not None and abs(delta) < abs(best):
                best = delta
        if best < np.inf:
            result[index] = best
    return result


def checkSnapsActive(snaps):
    for snap in snaps:
        snap.checkSnapActive()


def getSnaps(targets, dir, no_height=False):
    snaps = []
    targets = [t.target for t in targets]
    #if isinstance(target, TargetWrapper):
    #    target = target.target
    for target in targets:
        if isinstance(target, Text):
            for ax in target.figure.axes + [target.figure]:
                for txt in ax.texts:
                    # for other texts
                    if txt in targets:
                        continue
                    # snap to the x and the y coordinate
                    x, y = txt.get_transform().transform(txt.get_position())
                    snaps.append(snapSamePos(target, txt, 0))
                    snaps.append(snapSamePos(target, txt, 1))
            continue
        for index, axes in enumerate(target.figure.axes):
            if axes not in targets:
                # axes edged
                if dir & DIR_X0:
                    snaps.append(snapSameEdge(target, axes, 0))
                if dir & DIR_Y0:
                    snaps.append(snapSameEdge(target, axes, 1))
                if dir & DIR_X1:
                    snaps.append(snapSameEdge(target, axes, 2))
                if dir & DIR_Y1:
                    snaps.append(snapSameEdge(target, axes, 3))

                # snap same dimensions
                if not no_height:
                    if dir & DIR_X0:
                        snaps.append(snapSameDimension(target, axes, 0))
                    if dir & DIR_X1:
                        snaps.append(snapSameDimension(target, axes, 2))
                    if dir & DIR_Y0:
                        snaps.append(snapSameDimension(target, axes, 1))
                    if dir & DIR_Y1:
                        snaps.append(snapSameDimension(target, axes, 3))

                for axes2 in target.figure.axes:
                    if axes2 != axes and axes2 not in targets:
                        snaps.append(snapSameBorder(target, axes, axes2, dir))
    return snaps
