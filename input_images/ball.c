/*
 * Author: John Salame
 */
#include "objects.h"

/*
 * Adapted from example 13
 *  Draw a ball
 *     at (x,y,z)
 *     radius (r)
 */
void ball(double x,double y,double z,double r)
{
  int inc = 15;
  // Save transformation
  glPushMatrix();
  // Offset, scale and rotate
  glTranslated(x,y,z);
  glScaled(r,r,r);
  // White ball with yellow specular
  glColor3f(1,1,1);
  // Bands of latitude
  for (int ph=-90;ph<90;ph+=inc)
  {
    glBegin(GL_QUAD_STRIP);
    for (int th=0;th<=360;th+=2*inc)
    {
      Vertex(th,ph);
      Vertex(th,ph+inc);
    }
    glEnd();
  }
  // Undo transofrmations
  glPopMatrix();
}

/*
 *  Draw vertex in polar coordinates with normal
 */
void Vertex(double th,double ph)
{
  double x = Sin(th)*Cos(ph);
  double y = Cos(th)*Cos(ph);
  double z =         Sin(ph);
  //  For a sphere at the origin, the position
  //  and normal vectors are the same
  glNormal3d(x,y,z);
  glVertex3d(x,y,z);
}

